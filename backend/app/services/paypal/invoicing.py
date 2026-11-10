from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.agreement import Agreement
from app.models.audit import AuditLog
from app.models.invoice import Invoice
from app.models.milestone import Milestone
from app.services.payment_readiness import require_payment_readiness
from app.services.paypal.client import PaypalAPIError, PaypalClient
from app.state_machine.exceptions import InvalidTransitionError
from app.state_machine.milestone_fsm import (
    MilestoneStatus,
    validate_milestone_transition,
)
from app.state_machine.agreement_fsm import (
    AgreementStatus,
    validate_agreement_transition,
)

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)\b(authorization|access[_ -]?token|client[_ -]?secret|password)"
    r"\s*[:=]\s*[^\s,;]+"
)
_AUTH_SCHEME_RE = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/-]+=*")


def _safe_error_field(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "none"
    return re.sub(r"[^A-Za-z0-9._:-]", "_", value[:100])


def redacted_invoice_error_message(exc: Exception) -> str:
    if isinstance(exc, (PaypalAPIError, ValueError, InvalidTransitionError)):
        message = str(exc)
    else:
        message = "Unexpected integration or persistence error."
    message = _EMAIL_RE.sub("[redacted email]", message)
    message = _URL_RE.sub("[redacted URL]", message)
    message = _SENSITIVE_VALUE_RE.sub(r"\1=[redacted]", message)
    message = _AUTH_SCHEME_RE.sub(r"\1 [redacted]", message)
    return re.sub(r"[\r\n\t]+", " ", message)[:200]


def log_invoice_operation_failure(step: str, exc: Exception) -> None:
    paypal_error = exc if isinstance(exc, PaypalAPIError) else None
    logger.error(
        "paypal_invoice_operation_failed step=%s exception_class=%s message=%s "
        "status_code=%s error_name=%s issues=%s debug_id=%s",
        _safe_error_field(step),
        type(exc).__name__,
        redacted_invoice_error_message(exc),
        paypal_error.status_code if paypal_error and paypal_error.status_code is not None else "none",
        _safe_error_field(paypal_error.error_name) if paypal_error else "none",
        ",".join(_safe_error_field(issue) for issue in paypal_error.issues[:5])
        if paypal_error and paypal_error.issues
        else "none",
        _safe_error_field(paypal_error.debug_id) if paypal_error else "none",
    )


def build_invoice_payload(
    milestone: Milestone,
    invoice_id: str,
    recipient_email: str,
) -> dict[str, Any]:
    if milestone.amount_cents <= 0:
        raise ValueError("Invoice amount must be greater than zero.")
    if not recipient_email.strip():
        raise ValueError("Invoice recipient email is required.")

    amount = Decimal(milestone.amount_cents) / Decimal(100)
    return {
        "detail": {
            "invoice_number": f"ORC-{invoice_id[:12]}",
            "currency_code": milestone.agreement.currency,
            "note": "Payment for the approved Orchestra AI milestone.",
        },
        "primary_recipients": [
            {"billing_info": {"email_address": recipient_email.strip()}}
        ],
        "items": [
            {
                "name": milestone.title,
                "description": milestone.description or milestone.title,
                "quantity": "1",
                "unit_amount": {
                    "currency_code": milestone.agreement.currency,
                    "value": f"{amount:.2f}",
                },
            }
        ],
    }


def create_or_retry_invoice(
    db: Session,
    milestone: Milestone,
    recipient_email: str,
    paypal: PaypalClient,
) -> Invoice:
    operation = {"step": "validate_invoice_request"}
    try:
        return _create_or_retry_invoice(
            db, milestone, recipient_email, paypal, operation
        )
    except Exception as exc:
        log_invoice_operation_failure(operation["step"], exc)
        setattr(exc, "invoice_step", operation["step"])
        raise


def _create_or_retry_invoice(
    db: Session,
    milestone: Milestone,
    recipient_email: str,
    paypal: PaypalClient,
    operation: dict[str, str],
) -> Invoice:
    operation["step"] = "validate_invoice_request"
    if milestone.amount_cents <= 0:
        raise ValueError("Invoice amount must be greater than zero.")
    if not recipient_email.strip():
        raise ValueError("Invoice recipient email is required.")
    operation["step"] = "load_invoice_state"
    db.refresh(milestone, with_for_update=True)
    current_status = MilestoneStatus(milestone.status)
    approval = (
        db.query(Approval)
        .filter(Approval.milestone_id == milestone.id, Approval.decision == "approved")
        .order_by(Approval.created_at.desc())
        .first()
    )
    if approval is None:
        raise InvalidTransitionError(
            "Milestone", milestone.status, "INVOICING", "recorded client approval is required"
        )

    invoice = (
        db.query(Invoice)
        .filter(Invoice.milestone_id == milestone.id)
        .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .with_for_update()
        .first()
    )

    if invoice and invoice.status in {"SENT", "PAID"}:
        if not invoice.paypal_invoice_id:
            raise ValueError("Existing invoice is missing its PayPal invoice ID.")
        operation["step"] = "verify_existing_invoice_status"
        remote_invoice = paypal.get_invoice(invoice.paypal_invoice_id)
        if (
            remote_invoice.get("id") != invoice.paypal_invoice_id
            or not isinstance(remote_invoice.get("status"), str)
        ):
            raise PaypalAPIError("PayPal Sandbox returned an unexpected invoice.")
        apply_paypal_invoice_status(db, invoice, remote_invoice["status"])
        if not invoice.paypal_invoice_url and invoice.paypal_invoice_id:
            invoice.paypal_invoice_url = _payer_view_url(
                {}, invoice.paypal_invoice_id
            )
        db.commit()
        db.refresh(invoice)
        return invoice

    require_payment_readiness(db, milestone)

    if current_status not in {
        MilestoneStatus.APPROVED,
        MilestoneStatus.INVOICING,
        MilestoneStatus.INVOICE_CANCELLED,
        MilestoneStatus.INVOICE_EXPIRED,
    }:
        raise InvalidTransitionError(
            "Milestone", milestone.status, "INVOICING", "milestone is not approved for invoicing"
        )

    reusable_draft = bool(invoice and invoice.status == "DRAFT")
    if not reusable_draft:
        operation["step"] = "save_draft_to_db"
        invoice = Invoice(
            milestone_id=milestone.id,
            paypal_request_id=str(uuid4()),
            amount_cents=milestone.amount_cents,
            currency=milestone.agreement.currency,
            status="DRAFT",
        )
        db.add(invoice)
        db.flush()

    if current_status != MilestoneStatus.INVOICING:
        validate_milestone_transition(
            current_status,
            MilestoneStatus.INVOICING,
            user_role=None,
        )
        milestone.status = MilestoneStatus.INVOICING.value
    operation["step"] = "save_draft_to_db"
    db.commit()
    db.refresh(invoice)

    try:
        recovered_remote_invoice: dict[str, Any] | None = None
        if not invoice.paypal_invoice_id:
            operation["step"] = "build_payload"
            payload = build_invoice_payload(milestone, invoice.id, recipient_email)
            operation["step"] = "find_existing_invoice"
            recovered_remote_invoice = _find_reusable_remote_invoice(
                paypal,
                payload,
                recipient_email,
            )
            if recovered_remote_invoice is not None:
                paypal_invoice_id = recovered_remote_invoice["id"]
                logger.info(
                    "paypal_invoice_recovered local_invoice_id=%s paypal_invoice_id=%s",
                    invoice.id,
                    paypal_invoice_id,
                )
            else:
                try:
                    operation["step"] = "create_draft"
                    created = paypal.create_invoice(
                        payload, invoice.paypal_request_id
                    )
                except PaypalAPIError as create_error:
                    if (
                        create_error.status_code != 422
                        or "DUPLICATE_INVOICE_NUMBER" not in create_error.issues
                    ):
                        raise
                    operation["step"] = "find_existing_invoice"
                    recovered_remote_invoice = _find_reusable_remote_invoice(
                        paypal,
                        payload,
                        recipient_email,
                    )
                    if recovered_remote_invoice is None:
                        raise create_error
                    paypal_invoice_id = recovered_remote_invoice["id"]
                    logger.info(
                        "paypal_invoice_recovered local_invoice_id=%s paypal_invoice_id=%s",
                        invoice.id,
                        paypal_invoice_id,
                    )
                else:
                    paypal_invoice_id = created.get("id")
            if not isinstance(paypal_invoice_id, str) or not paypal_invoice_id:
                raise PaypalAPIError("PayPal Sandbox did not return an invoice ID.")
            invoice.paypal_invoice_id = paypal_invoice_id
            operation["step"] = "save_paypal_invoice_id"
            db.commit()
        if recovered_remote_invoice is not None:
            operation["step"] = "verify_existing_invoice"
            _verify_reusable_remote_invoice(
                recovered_remote_invoice,
                invoice.paypal_invoice_id,
                build_invoice_payload(milestone, invoice.id, recipient_email),
                recipient_email,
            )

        if recovered_remote_invoice is not None and recovered_remote_invoice.get(
            "status"
        ) in {"SENT", "PAID"}:
            remote_status = recovered_remote_invoice["status"]
            apply_paypal_invoice_status(db, invoice, remote_status)
            sent = recovered_remote_invoice
        else:
            send_request_id = str(uuid5(NAMESPACE_URL, f"orchestra-invoice-send:{invoice.id}"))
            operation["step"] = "send_invoice"
            sent = paypal.send_invoice(invoice.paypal_invoice_id, send_request_id)
        db.refresh(invoice, with_for_update=True)
        if invoice.status != "PAID":
            invoice.status = "SENT"
        payer_view_url = _payer_view_url(sent, invoice.paypal_invoice_id)
        if not payer_view_url and not invoice.paypal_invoice_url:
            operation["step"] = "fetch_invoice_details"
            details = paypal.get_invoice(invoice.paypal_invoice_id)
            remote_status = details.get("status")
            if isinstance(remote_status, str):
                apply_paypal_invoice_status(db, invoice, remote_status)
            payer_view_url = _payer_view_url(details, invoice.paypal_invoice_id)
        if payer_view_url:
            invoice.paypal_invoice_url = payer_view_url

        db.refresh(milestone, with_for_update=True)
        if milestone.status == MilestoneStatus.INVOICING.value:
            validate_milestone_transition(
                MilestoneStatus.INVOICING,
                MilestoneStatus.PAYMENT_PENDING,
                user_role=None,
            )
            milestone.status = MilestoneStatus.PAYMENT_PENDING.value
        operation["step"] = "save_invoice_state_to_db"
        db.commit()
        db.refresh(invoice)
        return invoice
    except Exception:
        db.rollback()
        db.refresh(milestone)
        if milestone.status == MilestoneStatus.INVOICING.value:
            milestone.status = MilestoneStatus.APPROVED.value
            db.commit()
        raise


def _find_reusable_remote_invoice(
    paypal: PaypalClient,
    payload: dict[str, Any],
    recipient_email: str,
) -> dict[str, Any] | None:
    invoice_number = payload["detail"]["invoice_number"]
    search_result = paypal.search_invoices(invoice_number)
    if not isinstance(search_result, dict):
        raise PaypalAPIError(
            "PayPal Sandbox returned an invalid invoice search result "
            f"(result has type {type(search_result).__name__})."
        )
    if not search_result:
        return None
    if not isinstance(search_result.get("items"), list):
        items = search_result.get("items")
        result_shape = (
            "items missing"
            if "items" not in search_result
            else f"items has type {type(items).__name__}"
        )
        result_shape += (
            "; top-level keys="
            + ",".join(
                sorted(
                    key
                    for key in search_result
                    if isinstance(key, str)
                )[:20]
            )
        )
        raise PaypalAPIError(
            f"PayPal Sandbox returned an invalid invoice search result ({result_shape})."
        )
    matches = [
        item
        for item in search_result["items"]
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("detail"), dict)
        and item["detail"].get("invoice_number") == invoice_number
    ]
    if len(matches) > 1:
        raise PaypalAPIError(
            "Multiple PayPal Sandbox invoices match this milestone; refusing to send."
        )
    if not matches:
        return None

    invoice_id = matches[0]["id"]
    remote_invoice = paypal.get_invoice(invoice_id)
    _verify_reusable_remote_invoice(
        remote_invoice,
        invoice_id,
        payload,
        recipient_email,
    )
    return remote_invoice


def _verify_reusable_remote_invoice(
    remote_invoice: dict[str, Any],
    invoice_id: str,
    payload: dict[str, Any],
    recipient_email: str,
) -> None:
    detail = remote_invoice.get("detail")
    recipients = remote_invoice.get("primary_recipients")
    items = remote_invoice.get("items")
    expected_detail = payload["detail"]
    expected_item = payload["items"][0]
    if (
        remote_invoice.get("id") != invoice_id
        or not isinstance(detail, dict)
        or detail.get("invoice_number") != expected_detail["invoice_number"]
        or detail.get("currency_code") != expected_detail["currency_code"]
    ):
        raise PaypalAPIError(
            "Matching PayPal Sandbox invoice has unexpected invoice details."
        )
    if not isinstance(recipients, list) or not any(
        isinstance(entry, dict)
        and isinstance(entry.get("billing_info"), dict)
        and isinstance(entry["billing_info"].get("email_address"), str)
        and entry["billing_info"]["email_address"].casefold()
        == recipient_email.strip().casefold()
        for entry in recipients
    ):
        raise PaypalAPIError(
            "Matching PayPal Sandbox invoice has an unexpected recipient."
        )
    if not isinstance(items, list) or len(items) != 1:
        raise PaypalAPIError(
            "Matching PayPal Sandbox invoice has unexpected line items."
        )

    item = items[0]
    amount = item.get("unit_amount") if isinstance(item, dict) else None
    try:
        amount_matches = (
            Decimal(amount["value"])
            == Decimal(expected_item["unit_amount"]["value"])
        )
    except (KeyError, ArithmeticError, TypeError, ValueError):
        amount_matches = False
    if (
        not isinstance(item, dict)
        or item.get("name") != expected_item["name"]
        or str(item.get("quantity")) != expected_item["quantity"]
        or not isinstance(amount, dict)
        or amount.get("currency_code")
        != expected_item["unit_amount"]["currency_code"]
        or not amount_matches
    ):
        raise PaypalAPIError(
            "Matching PayPal Sandbox invoice does not match the milestone amount."
        )
    if remote_invoice.get("status") not in {"DRAFT", "SENT", "PAID"}:
        raise PaypalAPIError(
            "Matching PayPal Sandbox invoice is not in a reusable state."
        )


def _payer_view_url(resource: dict[str, Any], invoice_id: str) -> str:
    links = resource.get("links", [])
    if not isinstance(links, list):
        return None
    for link in links:
        if isinstance(link, dict) and link.get("rel") == "payer-view":
            href = link.get("href")
            if isinstance(href, str):
                return href
    return (
        "https://www.sandbox.paypal.com/invoice/payerView/details/"
        + quote(invoice_id, safe="")
    )


def apply_paypal_invoice_status(
    db: Session,
    invoice: Invoice,
    paypal_status: str,
) -> None:
    status = paypal_status.upper()
    status_map = {
        "DRAFT": "DRAFT",
        "SENT": "SENT",
        "PAID": "PAID",
        "CANCELLED": "CANCELLED",
        "EXPIRED": "EXPIRED",
    }
    if status not in status_map:
        raise ValueError(f"Unsupported PayPal invoice status: {paypal_status}")

    milestone = db.get(Milestone, invoice.milestone_id)
    if milestone is None:
        raise ValueError("Invoice is not linked to a milestone.")
    db.refresh(milestone, with_for_update=True)
    db.refresh(invoice, with_for_update=True)

    mapped_status = status_map[status]
    if invoice.status == "PAID" and mapped_status != "PAID":
        return

    current = MilestoneStatus(milestone.status)
    target_by_invoice = {
        "PAID": MilestoneStatus.PAID,
        "CANCELLED": MilestoneStatus.INVOICE_CANCELLED,
        "EXPIRED": MilestoneStatus.INVOICE_EXPIRED,
    }
    target = target_by_invoice.get(mapped_status)
    if mapped_status in {"CANCELLED", "EXPIRED"} and current == MilestoneStatus.PAID:
        invoice.status = mapped_status
        return
    if target is not None and current != target:
        if target == MilestoneStatus.PAID and current in {
            MilestoneStatus.APPROVED,
            MilestoneStatus.INVOICING,
            MilestoneStatus.INVOICE_CANCELLED,
            MilestoneStatus.INVOICE_EXPIRED,
        }:
            validate_milestone_transition(
                current, MilestoneStatus.PAYMENT_PENDING, user_role=None
            )
            milestone.status = MilestoneStatus.PAYMENT_PENDING.value
            current = MilestoneStatus.PAYMENT_PENDING
        validate_milestone_transition(current, target, user_role=None)
        milestone.status = target.value
    elif mapped_status == "SENT" and current in {
        MilestoneStatus.APPROVED,
        MilestoneStatus.INVOICING,
    }:
        validate_milestone_transition(
            current, MilestoneStatus.PAYMENT_PENDING, user_role=None
        )
        milestone.status = MilestoneStatus.PAYMENT_PENDING.value
    invoice.status = mapped_status

    if mapped_status == "PAID":
        agreement = db.get(Agreement, milestone.agreement_id)
        if agreement is not None and agreement.status == AgreementStatus.ACTIVE.value:
            milestones = (
                db.query(Milestone)
                .filter(Milestone.agreement_id == agreement.id)
                .order_by(Milestone.order.asc())
                .all()
            )
            if milestones and all(item.status == MilestoneStatus.PAID.value for item in milestones):
                validate_agreement_transition(
                    AgreementStatus.ACTIVE,
                    AgreementStatus.COMPLETED,
                    milestones=[
                        {"title": item.title, "status": item.status}
                        for item in milestones
                    ],
                )
                agreement.status = AgreementStatus.COMPLETED.value
                db.add(
                    AuditLog(
                        agreement_id=agreement.id,
                        user_id=None,
                        action="agreement_completed",
                        entity_type="agreement",
                        entity_id=agreement.id,
                        details="{}",
                    )
                )
