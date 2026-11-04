import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_paypal_client
from app.models.invoice import Invoice
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


@router.post("/paypal")
async def receive_paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
    paypal: PaypalClient = Depends(get_paypal_client),
) -> dict[str, Any]:
    try:
        event = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("paypal_webhook_rejected reason=invalid_json")
        raise HTTPException(status_code=400, detail="Invalid webhook JSON.") from exc
    if not isinstance(event, dict):
        logger.warning("paypal_webhook_rejected reason=invalid_event_shape")
        raise HTTPException(status_code=400, detail="Webhook event must be a JSON object.")

    event_id = event.get("id")
    event_type = event.get("event_type")
    signature_headers = {name: request.headers.get(name) for name in SIGNATURE_HEADERS}
    if any(not value for value in signature_headers.values()):
        logger.warning(
            "paypal_webhook_rejected event_id=%s event_type=%s reason=missing_signature_headers",
            _log_field(event_id),
            _log_field(event_type),
        )
        raise HTTPException(status_code=400, detail="Required PayPal signature headers are missing.")

    try:
        if not paypal.verify_webhook(
            {name: value for name, value in signature_headers.items() if value is not None},
            event,
        ):
            logger.warning(
                "paypal_webhook_rejected event_id=%s event_type=%s reason=invalid_signature",
                _log_field(event_id),
                _log_field(event_type),
            )
            raise HTTPException(status_code=400, detail="PayPal webhook signature is invalid.")
    except PaypalAPIError as exc:
        logger.error(
            "paypal_webhook_verification_unavailable event_id=%s event_type=%s",
            _log_field(event_id),
            _log_field(event_type),
        )
        raise HTTPException(status_code=502, detail="PayPal webhook signature verification failed.") from exc
    except PaypalConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    resource = event.get("resource")
    if not isinstance(event_id, str) or not event_id or not isinstance(event_type, str):
        logger.warning(
            "paypal_webhook_rejected event_id=%s event_type=%s reason=missing_event_metadata signature_verified=true",
            _log_field(event_id),
            _log_field(event_type),
        )
        raise HTTPException(status_code=400, detail="PayPal event ID and type are required.")
    if not isinstance(resource, dict):
        logger.warning(
            "paypal_webhook_rejected event_id=%s event_type=%s reason=invalid_resource signature_verified=true",
            _log_field(event_id),
            _log_field(event_type),
        )
        raise HTTPException(status_code=400, detail="PayPal event resource is missing.")

    invoice_id = extract_paypal_invoice_id(event)
    existing = db.query(WebhookEvent).filter(WebhookEvent.paypal_event_id == event_id).first()
    if existing is not None:
        logger.info(
            "paypal_webhook_duplicate event_id=%s event_type=%s signature_verified=true",
            _log_field(event_id),
            _log_field(event_type),
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
        logger.info(
            "paypal_webhook_duplicate event_id=%s event_type=%s signature_verified=true",
            _log_field(event_id),
            _log_field(event_type),
        )
        return {"status": "duplicate", "event_id": event_id}

    target_status = PAYPAL_EVENT_STATUSES.get(event_type)
    if target_status and invoice_id:
        invoice = (
            db.query(Invoice)
            .filter(Invoice.paypal_invoice_id == invoice_id)
            .first()
        )
        if invoice is not None:
            try:
                apply_paypal_invoice_status(db, invoice, target_status)
            except (InvalidTransitionError, ValueError) as exc:
                db.rollback()
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            webhook_record.processed = "processed"
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
            logger.info(
                "paypal_webhook_duplicate event_id=%s event_type=%s signature_verified=true",
                _log_field(event_id),
                _log_field(event_type),
            )
            return {"status": "duplicate", "event_id": event_id}
        raise
    logger.info(
        "paypal_webhook_accepted event_id=%s event_type=%s signature_verified=true invoice_id=%s processed=%s",
        _log_field(event_id),
        _log_field(event_type),
        _log_field(invoice_id),
        webhook_record.processed,
    )
    return {"status": webhook_record.processed, "event_id": event_id}
