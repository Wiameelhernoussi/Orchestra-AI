from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
from urllib.parse import urlparse
from uuid import uuid4
from typing import Literal
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_paypal_client, get_settings
from app.config import Settings
from app.models.paywall_purchase import PaywallPurchase
from app.models.user import User
from app.services.paypal.client import PaypalAPIError, PaypalClient
from app.services.mock_integrations import MockPaypalClient
from app.services.groq_agents import CompletionProvider, GroqAgentClient
from app.services.paywall_assistant import get_offer, recommend_offers

logger = logging.getLogger(__name__)
FRONTEND_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}
PAYPAL_APPROVAL_HOSTS = {
    "www.sandbox.paypal.com",
    "sandbox.paypal.com",
    "checkout.sandbox.paypal.com",
}


def require_paywall_assistant_enabled(
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.PAYWALL_ASSISTANT_ENABLED:
        raise HTTPException(status_code=404, detail="Not found.")


router = APIRouter(
    prefix="/paywall",
    tags=["paywall assistant"],
    dependencies=[Depends(require_paywall_assistant_enabled)],
)


def get_paywall_recommendation_provider(
    settings: Settings = Depends(get_settings),
) -> Generator[CompletionProvider | None, None, None]:
    if settings.DEMO_MODE == "mock" or not settings.GROQ_API_KEY:
        yield None
        return
    provider = GroqAgentClient(
        settings.GROQ_API_KEY,
        max_retries=settings.GROQ_MAX_RETRIES,
        max_retry_wait_seconds=settings.GROQ_MAX_RETRY_WAIT_SECONDS,
    )
    try:
        yield provider
    finally:
        provider.close()


class PreferenceRequest(BaseModel):
    topics: list[Literal["productivity", "freelancing", "artificial-intelligence"]] = Field(
        default_factory=list,
        max_length=3,
    )
    max_budget_cents: int = Field(ge=0, le=5000)


class PurchaseRequest(BaseModel):
    offer_id: str
    max_budget_cents: int = Field(ge=0, le=5000)
    user_confirmed_purchase: bool


def _client_user(user: User) -> None:
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients can purchase content.")


def _approval_link(order: dict) -> str:
    if order.get("status") == "APPROVED":
        return ""
    links = order.get("links")
    if not isinstance(links, list):
        raise HTTPException(status_code=502, detail="PayPal Sandbox did not return an approval link.")
    for link in links:
        if not isinstance(link, dict) or link.get("rel") not in {"payer-action", "approve"}:
            continue
        href = link.get("href")
        parsed = urlparse(href) if isinstance(href, str) else None
        if parsed and parsed.scheme == "https" and parsed.hostname in PAYPAL_APPROVAL_HOSTS:
            return href
    raise HTTPException(status_code=502, detail="PayPal Sandbox did not return a valid approval link.")


def _capture_details(order: dict, purchase: PaywallPurchase) -> str:
    if order.get("id") != purchase.paypal_order_id or order.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail="PayPal has not confirmed this payment.")
    units = order.get("purchase_units")
    if not isinstance(units, list) or not units:
        raise HTTPException(status_code=502, detail="PayPal returned no captured purchase details.")
    payments = units[0].get("payments") if isinstance(units[0], dict) else None
    captures = payments.get("captures") if isinstance(payments, dict) else None
    if not isinstance(captures, list) or not captures or not isinstance(captures[0], dict):
        raise HTTPException(status_code=502, detail="PayPal returned no completed capture.")
    capture = captures[0]
    amount = capture.get("amount")
    expected_value = f"{Decimal(purchase.amount_cents) / Decimal(100):.2f}"
    if (
        capture.get("status") != "COMPLETED"
        or not isinstance(capture.get("id"), str)
        or not isinstance(amount, dict)
        or amount.get("currency_code") != purchase.currency
        or amount.get("value") != expected_value
    ):
        raise HTTPException(status_code=409, detail="PayPal payment details do not match this content purchase.")
    return capture["id"]


@router.post("/recommendations")
def get_recommendations(
    payload: PreferenceRequest,
    current_user: User = Depends(get_current_user),
    provider: CompletionProvider | None = Depends(get_paywall_recommendation_provider),
    settings: Settings = Depends(get_settings),
) -> dict:
    _client_user(current_user)
    deterministic = recommend_offers(payload.topics, payload.max_budget_cents)
    if not deterministic:
        return {
            "recommendations": [],
            "assistant_mode": "preference_match",
            "explanation": "No demo offer fits this budget. Increase your maximum to see options.",
        }
    if provider is None:
        assistant_mode = (
            "mock_rules"
            if settings.DEMO_MODE == "mock"
            else "rules_fallback"
        )
        return {
            "recommendations": deterministic,
            "assistant_mode": assistant_mode,
            "explanation": (
                "Mock mode uses a labeled, deterministic topic-and-budget match. Nothing is purchased automatically."
                if assistant_mode == "mock_rules"
                else "AI recommendations are unavailable, so offers are shown in deterministic topic-and-budget order. Nothing is purchased automatically."
            ),
        }
    eligible_ids = {offer["id"] for offer in deterministic}
    schema = {
        "type": "object",
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": sorted(eligible_ids)},
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["recommendations"],
        "additionalProperties": False,
    }
    try:
        result = provider.complete_json(
            model=settings.GROQ_COMPARE_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rank only the provided content offers for the user's declared "
                        "topics and maximum budget. Do not invent offers or prices. "
                        "Give one short reason per offer. This is only a recommendation; "
                        "never imply a purchase was made or authorized."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "topics": payload.topics,
                            "max_budget_cents": payload.max_budget_cents,
                            "offers": deterministic,
                        },
                        separators=(",", ":"),
                    ),
                },
            ],
            schema_name="paywall_recommendations",
            schema=schema,
            max_completion_tokens=250,
            reasoning_effort="low",
        )
        raw_recommendations = result.data.get("recommendations")
        if not isinstance(raw_recommendations, list):
            raise ValueError("The recommendation response had an invalid shape.")
        offer_map = {offer["id"]: offer for offer in deterministic}
        recommendations: list[dict] = []
        seen: set[str] = set()
        for item in raw_recommendations:
            if not isinstance(item, dict):
                continue
            offer_id = item.get("id")
            reason = item.get("reason")
            if (
                offer_id in eligible_ids
                and offer_id not in seen
                and isinstance(reason, str)
                and reason.strip()
            ):
                recommendations.append(
                    {**offer_map[offer_id], "reason": reason.strip()[:180]}
                )
                seen.add(offer_id)
        if not recommendations:
            raise ValueError("The recommendation response contained no eligible offers.")
        return {
            "recommendations": recommendations,
            "assistant_mode": "groq_ai",
            "explanation": "AI ranked offers using your selected topics and maximum budget. Nothing is purchased automatically.",
        }
    except (RuntimeError, ValueError, TypeError, KeyError) as exc:
        logger.warning(
            "paywall_recommendation_fallback exception_type=%s",
            type(exc).__name__,
        )
    return {
        "recommendations": deterministic,
        "assistant_mode": "rules_fallback",
        "explanation": "The AI recommendation was unavailable, so offers are shown in a deterministic topic-and-budget order. Nothing is purchased automatically.",
    }


@router.post("/purchases")
def create_purchase(
    payload: PurchaseRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paypal: PaypalClient = Depends(get_paypal_client),
) -> dict:
    _client_user(current_user)
    if not payload.user_confirmed_purchase:
        raise HTTPException(status_code=409, detail="Explicit confirmation is required before creating a PayPal order.")
    if isinstance(paypal, MockPaypalClient):
        raise HTTPException(status_code=409, detail="Content purchases require real PayPal Sandbox mode.")
    offer = get_offer(payload.offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Content offer not found.")
    if offer["price_cents"] > payload.max_budget_cents:
        raise HTTPException(status_code=409, detail="This offer exceeds your selected budget.")

    purchase = (
        db.query(PaywallPurchase)
        .filter(
            PaywallPurchase.user_id == current_user.id,
            PaywallPurchase.offer_id == offer["id"],
            PaywallPurchase.status == "PENDING",
        )
        .order_by(PaywallPurchase.created_at.desc())
        .first()
    )
    if purchase and purchase.paypal_order_id and purchase.approval_url:
        return {
            "purchase_id": purchase.id,
            "status": purchase.status,
            "approval_url": purchase.approval_url,
            "amount_cents": purchase.amount_cents,
            "currency": purchase.currency,
        }
    if purchase is None:
        purchase = PaywallPurchase(
            user_id=current_user.id,
            offer_id=offer["id"],
            create_request_id=str(uuid4()),
            capture_request_id=str(uuid4()),
            amount_cents=offer["price_cents"],
            currency=offer["currency"],
            status="PENDING",
        )
        db.add(purchase)
        db.commit()
        db.refresh(purchase)

    origin = request.headers.get("origin", "http://localhost:5173").rstrip("/")
    if origin not in FRONTEND_ORIGINS:
        raise HTTPException(status_code=400, detail="PayPal checkout can only be started from the local application.")
    return_url = f"{origin}/client/paywall?purchase_id={purchase.id}"
    try:
        order = paypal.create_order(
            {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": purchase.id,
                        "description": offer["title"],
                        "amount": {
                            "currency_code": purchase.currency,
                            "value": f"{Decimal(purchase.amount_cents) / Decimal(100):.2f}",
                        },
                    }
                ],
                "application_context": {
                    "brand_name": "Orchestra AI Demo",
                    "user_action": "PAY_NOW",
                    "return_url": return_url,
                    "cancel_url": f"{origin}/client/paywall?cancelled=1",
                },
            },
            purchase.create_request_id,
        )
        if not isinstance(order.get("id"), str):
            raise HTTPException(status_code=502, detail="PayPal Sandbox did not return an order ID.")
        approval_url = _approval_link(order)
        purchase.paypal_order_id = order["id"]
        purchase.approval_url = approval_url or None
        db.commit()
        return {
            "purchase_id": purchase.id,
            "status": "APPROVED" if not approval_url else "PENDING",
            "approval_url": approval_url or None,
            "amount_cents": purchase.amount_cents,
            "currency": purchase.currency,
        }
    except PaypalAPIError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="Could not create a PayPal Sandbox checkout order.") from exc


@router.post("/purchases/{purchase_id}/capture")
def capture_purchase(
    purchase_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paypal: PaypalClient = Depends(get_paypal_client),
) -> dict:
    _client_user(current_user)
    if isinstance(paypal, MockPaypalClient):
        raise HTTPException(status_code=409, detail="Content purchases require real PayPal Sandbox mode.")
    purchase = db.get(PaywallPurchase, purchase_id)
    if purchase is None or purchase.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Purchase not found.")
    offer = get_offer(purchase.offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Content offer not found.")
    if purchase.status != "CAPTURED":
        if not purchase.paypal_order_id:
            raise HTTPException(status_code=409, detail="PayPal checkout has not been started.")
        try:
            order = paypal.capture_order(
                purchase.paypal_order_id,
                purchase.capture_request_id,
            )
        except PaypalAPIError as exc:
            try:
                order = paypal.get_order(purchase.paypal_order_id)
            except PaypalAPIError:
                db.rollback()
                raise HTTPException(
                    status_code=502,
                    detail="PayPal Sandbox has not confirmed the content payment.",
                ) from exc
        purchase.paypal_capture_id = _capture_details(order, purchase)
        purchase.status = "CAPTURED"
        purchase.captured_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(purchase)
    return {
        "purchase_id": purchase.id,
        "status": purchase.status,
        "offer_id": purchase.offer_id,
        "title": offer["title"],
        "content": offer["content"],
        "captured_at": purchase.captured_at.isoformat() if purchase.captured_at else None,
    }
