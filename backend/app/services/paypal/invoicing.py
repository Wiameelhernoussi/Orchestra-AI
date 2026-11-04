from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.invoice import Invoice
from app.models.milestone import Milestone
from app.services.paypal.client import PaypalAPIError, PaypalClient
from app.state_machine.exceptions import InvalidTransitionError
from app.state_machine.milestone_fsm import (
    MilestoneStatus,
    validate_milestone_transition,
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
    if milestone.amount_cents <= 0:
        raise ValueError("Invoice amount must be greater than zero.")
    if not recipient_email.strip():
        raise ValueError("Invoice recipient email is required.")
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
        if current_status in {
            MilestoneStatus.APPROVED,
            MilestoneStatus.INVOICING,
        }:
            apply_paypal_invoice_status(db, invoice, invoice.status)
            db.commit()
            db.refresh(invoice)
        return invoice

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
    db.commit()
    db.refresh(invoice)

    try:
        if not invoice.paypal_invoice_id:
            created = paypal.create_invoice(
                build_invoice_payload(milestone, invoice.id, recipient_email),
                invoice.paypal_request_id,
            )
            paypal_invoice_id = created.get("id")
            if not isinstance(paypal_invoice_id, str) or not paypal_invoice_id:
                raise PaypalAPIError("PayPal Sandbox did not return an invoice ID.")
            invoice.paypal_invoice_id = paypal_invoice_id
            db.commit()

        send_request_id = str(uuid5(NAMESPACE_URL, f"orchestra-invoice-send:{invoice.id}"))
        sent = paypal.send_invoice(invoice.paypal_invoice_id, send_request_id)
        db.refresh(invoice, with_for_update=True)
        if invoice.status != "PAID":
            invoice.status = "SENT"
        payer_view_url = _payer_view_url(sent)
        if not payer_view_url and not invoice.paypal_invoice_url:
            details = paypal.get_invoice(invoice.paypal_invoice_id)
            remote_status = details.get("status")
            if isinstance(remote_status, str):
                apply_paypal_invoice_status(db, invoice, remote_status)
            payer_view_url = _payer_view_url(details)
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
        db.commit()
        db.refresh(invoice)
        return invoice
    except PaypalAPIError:
        db.rollback()
        db.refresh(milestone)
        if milestone.status == MilestoneStatus.INVOICING.value:
            milestone.status = MilestoneStatus.APPROVED.value
            db.commit()
        raise


def _payer_view_url(resource: dict[str, Any]) -> str | None:
    links = resource.get("links", [])
    if not isinstance(links, list):
        return None
    for link in links:
        if isinstance(link, dict) and link.get("rel") == "payer-view":
            href = link.get("href")
            if isinstance(href, str):
                return href
    return None


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
