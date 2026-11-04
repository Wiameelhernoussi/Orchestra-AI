import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_paypal_client
from app.models.agreement import Agreement
from app.models.audit import AuditLog
from app.models.invoice import Invoice
from app.models.milestone import Milestone
from app.models.milestone import Milestone
from app.models.webhook import WebhookEvent
from app.services.paypal.client import (
    PaypalAPIError,
    PaypalClient,
    PaypalConfigurationError,
)
from app.services.paypal.invoicing import apply_paypal_invoice_status
from app.state_machine.exceptions import InvalidTransitionError

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

SIGNATURE_HEADERS = (
    "paypal-auth-algo",
    "paypal-cert-url",
    "paypal-transmission-id",
    "paypal-transmission-sig",
    "paypal-transmission-time",
)

PAYPAL_EVENT_STATUSES = {
    "INVOICING.INVOICE.PAID": "PAID",
    "INVOICING.INVOICE.CANCELLED": "CANCELLED",
}

INVOICE_ID_PATHS = (
    ("resource", "invoice", "id"),
    ("resource", "invoice_id"),
    ("resource", "invoiceId"),
    ("resource", "id"),
)


def extract_paypal_invoice_id(event: dict[str, Any]) -> str | None:
    for path in INVOICE_ID_PATHS:
        value: Any = event
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    resource = event.get("resource")
    links = resource.get("links") if isinstance(resource, dict) else None
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict) or not isinstance(link.get("href"), str):
                continue
            match = re.search(r"/v2/invoicing/invoices/([^/?#]+)", link["href"])
            if match:
                return match.group(1)
    return None


def _log_field(value: Any) -> str:
    if not isinstance(value, str):
        return "none"
    return re.sub(r"[^A-Za-z0-9._:-]", "_", value[:120]) or "none"


def _log_webhook_delivery(
    event_id: Any,
    event_type: Any,
    *,
    signature_verified: bool | None,
    linked_milestone_id: str | None,
    response_code: int,
    outcome: str,
) -> None:
    verification = (
        "unknown" if signature_verified is None else str(signature_verified).lower()
    )
    logger.info(
        "paypal_webhook_delivery event_id=%s event_type=%s signature_verified=%s "
        "linked_milestone=%s response_code=%d outcome=%s",
        _log_field(event_id),
        _log_field(event_type),
        verification,
        _log_field(linked_milestone_id),
        response_code,
        _log_field(outcome),
    )


@router.post("/paypal")
async def receive_paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
    paypal: PaypalClient = Depends(get_paypal_client),
) -> dict[str, Any]:
    try:
        event = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        _log_webhook_delivery(
            None,
            None,
            signature_verified=False,
            linked_milestone_id=None,
            response_code=400,
            outcome="invalid_json",
        )
        raise HTTPException(status_code=400, detail="Invalid webhook JSON.") from exc
    if not isinstance(event, dict):
        _log_webhook_delivery(
            None,
            None,
            signature_verified=False,
            linked_milestone_id=None,
            response_code=400,
            outcome="invalid_event_shape",
        )
        raise HTTPException(status_code=400, detail="Webhook event must be a JSON object.")

    event_id = event.get("id")
    event_type = event.get("event_type")
    signature_headers = {name: request.headers.get(name) for name in SIGNATURE_HEADERS}
    if any(not value for value in signature_headers.values()):
        _log_webhook_delivery(
            event_id,
            event_type,
            signature_verified=False,
            linked_milestone_id=None,
            response_code=400,
            outcome="missing_signature_headers",
        )
        raise HTTPException(status_code=400, detail="Required PayPal signature headers are missing.")

    try:
        if not paypal.verify_webhook(
            {name: value for name, value in signature_headers.items() if value is not None},
            event,
        ):
            _log_webhook_delivery(
                event_id,
                event_type,
                signature_verified=False,
                linked_milestone_id=None,
                response_code=400,
                outcome="invalid_signature",
            )
            raise HTTPException(status_code=400, detail="PayPal webhook signature is invalid.")
    except PaypalAPIError as exc:
        _log_webhook_delivery(
            event_id,
            event_type,
            signature_verified=None,
            linked_milestone_id=None,
            response_code=502,
            outcome="verification_unavailable",
        )
        raise HTTPException(status_code=502, detail="PayPal webhook signature verification failed.") from exc
    except PaypalConfigurationError as exc:
        _log_webhook_delivery(
            event_id,
            event_type,
            signature_verified=None,
            linked_milestone_id=None,
            response_code=503,
            outcome="verification_misconfigured",
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    resource = event.get("resource")
    if not isinstance(event_id, str) or not event_id or not isinstance(event_type, str):
        _log_webhook_delivery(
            event_id,
            event_type,
            signature_verified=True,
            linked_milestone_id=None,
            response_code=400,
            outcome="missing_event_metadata",
        )
        raise HTTPException(status_code=400, detail="PayPal event ID and type are required.")
    if not isinstance(resource, dict):
        _log_webhook_delivery(
            event_id,
            event_type,
            signature_verified=True,
            linked_milestone_id=None,
            response_code=400,
            outcome="invalid_resource",
        )
        raise HTTPException(status_code=400, detail="PayPal event resource is missing.")

    invoice_id = extract_paypal_invoice_id(event)
    invoice = (
        db.query(Invoice)
        .filter(Invoice.paypal_invoice_id == invoice_id)
        .first()
        if invoice_id
        else None
    )
    linked_milestone_id = invoice.milestone_id if invoice is not None else None
    existing = db.query(WebhookEvent).filter(WebhookEvent.paypal_event_id == event_id).first()
    if existing is not None:
        _log_webhook_delivery(
            event_id,
            event_type,
            signature_verified=True,
            linked_milestone_id=linked_milestone_id,
            response_code=200,
            outcome="duplicate",
        )
        return {"status": "duplicate", "event_id": event_id}

    webhook_record = WebhookEvent(
        paypal_event_id=event_id,
        event_type=event_type,
        resource_id=invoice_id,
        raw_payload=json.dumps(event, separators=(",", ":"), sort_keys=True),
        processed="pending",
    )
    db.add(webhook_record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        _log_webhook_delivery(
            event_id,
            event_type,
            signature_verified=True,
            linked_milestone_id=linked_milestone_id,
            response_code=200,
            outcome="duplicate",
        )
        return {"status": "duplicate", "event_id": event_id}

    target_status = PAYPAL_EVENT_STATUSES.get(event_type)
    if target_status and invoice_id:
        if invoice is not None:
            try:
                apply_paypal_invoice_status(db, invoice, target_status)
            except (InvalidTransitionError, ValueError) as exc:
                db.rollback()
                _log_webhook_delivery(
                    event_id,
                    event_type,
                    signature_verified=True,
                    linked_milestone_id=linked_milestone_id,
                    response_code=409,
                    outcome="invalid_transition",
                )
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            webhook_record.processed = "processed"
            milestone = db.get(Milestone, invoice.milestone_id)
            if milestone is not None:
                agreement = db.get(Agreement, milestone.agreement_id)
                if agreement is not None:
                    db.add(
                        AuditLog(
                            agreement_id=agreement.id,
                            user_id=None,
                            action="paypal_invoice_status_updated",
                            entity_type="invoice",
                            entity_id=invoice.id,
                            details=json.dumps(
                                {
                                    "event_id": event_id,
                                    "event_type": event_type,
                                    "status": target_status,
                                },
                                separators=(",", ":"),
                            ),
                        )
                    )
        else:
            webhook_record.processed = "ignored"
    else:
        webhook_record.processed = "ignored"

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(WebhookEvent).filter(WebhookEvent.paypal_event_id == event_id).first()
        if existing is not None:
            _log_webhook_delivery(
                event_id,
                event_type,
                signature_verified=True,
                linked_milestone_id=linked_milestone_id,
                response_code=200,
                outcome="duplicate",
            )
            return {"status": "duplicate", "event_id": event_id}
        raise
    _log_webhook_delivery(
        event_id,
        event_type,
        signature_verified=True,
        linked_milestone_id=linked_milestone_id,
        response_code=200,
        outcome=webhook_record.processed,
    )
    return {"status": webhook_record.processed, "event_id": event_id}
