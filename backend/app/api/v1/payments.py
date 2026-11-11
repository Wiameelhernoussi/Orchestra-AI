import base64
import binascii
import json
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_paypal_client, get_settings
from app.config import Settings
from app.models.approval import Approval
from app.models.agreement import Agreement
from app.models.audit import AuditLog
from app.models.invoice import Invoice
from app.models.milestone import Milestone
from app.models.user import User
from app.models.webhook import WebhookEvent
from app.services.paypal.client import PaypalAPIError, PaypalClient
from app.services.mock_integrations import MockPaypalClient
from app.services.paypal.invoicing import (
    apply_paypal_invoice_status,
    create_or_retry_invoice,
    log_invoice_operation_failure,
    redacted_invoice_error_message,
)
from app.services.payment_readiness import PaymentNotReadyError, calculate_payment_readiness
from app.state_machine.exceptions import InvalidTransitionError

router = APIRouter(prefix="/payments", tags=["payments"])


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    milestone_id: str
    paypal_invoice_id: str | None
    amount_cents: int
    currency: str
    status: str
    paypal_invoice_url: str | None
    sent_at: datetime | None = None
    last_reminder_at: datetime | None = None
    last_reminder_status: str | None = None


class PaymentTotalsResponse(BaseModel):
    total_invoiced_cents: int
    paid_cents: int
    pending_cents: int


@router.get("/summary", response_model=PaymentTotalsResponse)
def get_payment_totals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    if current_user.role not in {"client", "provider"}:
        raise HTTPException(status_code=403, detail="Payment totals are available to agreement members.")

    agreement_org_column = (
        Agreement.client_org_id if current_user.role == "client" else Agreement.provider_org_id
    )
    totals = (
        db.query(
            func.coalesce(func.sum(Invoice.amount_cents), 0).label("total_invoiced"),
            func.coalesce(
                func.sum(case((Invoice.status == "PAID", Invoice.amount_cents), else_=0)),
                0,
            ).label("paid"),
            func.coalesce(
                func.sum(
                    case(
                        (Invoice.status.in_(("DRAFT", "SENT")), Invoice.amount_cents),
                        else_=0,
                    )
                ),
                0,
            ).label("pending"),
        )
        .join(Milestone, Invoice.milestone_id == Milestone.id)
        .join(Agreement, Milestone.agreement_id == Agreement.id)
        .filter(
            agreement_org_column == current_user.organization_id,
            Invoice.paypal_invoice_id.is_not(None),
        )
        .one()
    )
    return {
        "total_invoiced_cents": int(totals.total_invoiced),
        "paid_cents": int(totals.paid),
        "pending_cents": int(totals.pending),
    }


@router.post("/milestones/{milestone_id}/invoice", response_model=InvoiceResponse)
def create_milestone_invoice(
    milestone_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paypal: PaypalClient = Depends(get_paypal_client),
) -> Invoice:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found.")
    agreement = db.get(Agreement, milestone.agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found.")
    if current_user.role != "client" or current_user.organization_id != agreement.client_org_id:
        raise HTTPException(status_code=403, detail="Only the agreement client can request its invoice.")

    approvals = (
        db.query(Approval)
        .filter(Approval.milestone_id == milestone.id, Approval.decision == "approved")
        .order_by(Approval.created_at.desc())
        .all()
    )
    approving_users = [db.get(User, approval.approved_by) for approval in approvals]
    if not any(
        approver is not None
        and approver.role == "client"
        and approver.organization_id == agreement.client_org_id
        for approver in approving_users
    ):
        raise HTTPException(status_code=409, detail="A recorded client approval is required before invoicing.")

    try:
        readiness = calculate_payment_readiness(db, milestone)
        if not readiness["ready"] or not readiness["paypal_invoice_allowed"]:
            reasons = " ".join(readiness["blocking_reasons"])
            raise PaymentNotReadyError(
                {
                    **readiness,
                    "blocking_reasons": readiness["blocking_reasons"]
                    or [reasons or "The milestone is not eligible for invoicing."],
                }
            )
        invoice = create_or_retry_invoice(db, milestone, current_user.email, paypal)
        try:
            db.add(
                AuditLog(
                    agreement_id=agreement.id,
                    user_id=current_user.id,
                    action="invoice_created_or_retried",
                    entity_type="invoice",
                    entity_id=invoice.id,
                    details='{"provider":"paypal_sandbox"}',
                )
            )
            db.commit()
            db.refresh(invoice)
        except SQLAlchemyError as exc:
            db.rollback()
            log_invoice_operation_failure("save_audit_log_to_db", exc)
            raise HTTPException(
                status_code=502,
                detail="Invoice was created but could not be fully recorded. Retrying is safe.",
            ) from exc
        return invoice
    except PaymentNotReadyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PaypalAPIError as exc:
        db.rollback()
        step = getattr(exc, "invoice_step", "paypal_request")
        reason = redacted_invoice_error_message(exc)
        raise HTTPException(
            status_code=502,
            detail=(
                f"Invoice operation failed during {step}: {reason} "
                "Approval is preserved; retrying is safe."
            ),
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        step = getattr(exc, "invoice_step", "save_invoice_state_to_db")
        raise HTTPException(
            status_code=502,
            detail=(
                f"Invoice operation failed during {step}: the invoice could not "
                "be saved. Approval is preserved; retrying is safe."
            ),
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422, detail=redacted_invoice_error_message(exc)
        ) from exc


@router.post("/invoices/{invoice_id}/sync", response_model=InvoiceResponse)
def sync_invoice_status(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paypal: PaypalClient = Depends(get_paypal_client),
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    milestone = db.get(Milestone, invoice.milestone_id)
    agreement = db.get(Agreement, milestone.agreement_id) if milestone else None
    if agreement is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if current_user.organization_id not in {agreement.client_org_id, agreement.provider_org_id}:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if not invoice.paypal_invoice_id:
        raise HTTPException(status_code=409, detail="Invoice has not been created in PayPal.")

    try:
        remote_invoice = paypal.get_invoice(invoice.paypal_invoice_id)
        remote_id = remote_invoice.get("id")
        remote_status = remote_invoice.get("status")
        if remote_id != invoice.paypal_invoice_id or not isinstance(remote_status, str):
            raise PaypalAPIError("PayPal Sandbox returned an unexpected invoice.")
        apply_paypal_invoice_status(db, invoice, remote_status)
        status_source = "mock_client" if isinstance(paypal, MockPaypalClient) else "paypal_api"
        db.add(
            AuditLog(
                agreement_id=agreement.id,
                user_id=current_user.id,
                action="invoice_status_synchronized",
                entity_type="invoice",
                entity_id=invoice.id,
                details=json.dumps(
                    {"source": status_source, "status": remote_status},
                    separators=(",", ":"),
                ),
            )
        )
        db.commit()
        db.refresh(invoice)
        return invoice
    except PaypalAPIError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail="Could not synchronize invoice with PayPal Sandbox.") from exc
    except (InvalidTransitionError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/invoices/{invoice_id}/qr-code")
def get_invoice_qr_code(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paypal: PaypalClient = Depends(get_paypal_client),
) -> dict[str, str]:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or not invoice.paypal_invoice_id:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    milestone = db.get(Milestone, invoice.milestone_id)
    agreement = db.get(Agreement, milestone.agreement_id) if milestone else None
    if (
        agreement is None
        or current_user.role != "client"
        or current_user.organization_id != agreement.client_org_id
    ):
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if invoice.status != "SENT":
        raise HTTPException(status_code=409, detail="A payment QR code is available only for an unpaid sent invoice.")
    if isinstance(paypal, MockPaypalClient):
        raise HTTPException(status_code=404, detail="PayPal Sandbox QR codes are unavailable in mock mode.")
    try:
        result = paypal.generate_invoice_qr_code(invoice.paypal_invoice_id)
        encoded_image = result.get("image")
        if not isinstance(encoded_image, str) or not encoded_image:
            raise PaypalAPIError("PayPal Sandbox returned no QR code image.")
        decoded_image = base64.b64decode(encoded_image, validate=True)
        if not decoded_image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise PaypalAPIError("PayPal Sandbox returned an invalid QR code image.")
    except (PaypalAPIError, binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="PayPal Sandbox could not generate a payment QR code.",
        ) from exc
    return {"qr_code_base64": encoded_image, "content_type": "image/png"}


@router.post("/invoices/{invoice_id}/reminder")
def send_invoice_reminder(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paypal: PaypalClient = Depends(get_paypal_client),
) -> dict[str, str | None]:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or not invoice.paypal_invoice_id:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    milestone = db.get(Milestone, invoice.milestone_id)
    agreement = db.get(Agreement, milestone.agreement_id) if milestone else None
    if (
        agreement is None
        or current_user.role != "provider"
        or current_user.organization_id != agreement.provider_org_id
    ):
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if isinstance(paypal, MockPaypalClient):
        raise HTTPException(status_code=404, detail="PayPal Sandbox reminders are unavailable in mock mode.")

    db.refresh(invoice, with_for_update=True)
    if invoice.status != "SENT":
        raise HTTPException(status_code=409, detail="Reminders are available only while an invoice is awaiting payment.")
    now = datetime.now(timezone.utc)
    last_reminder_at = invoice.last_reminder_at
    if last_reminder_at is not None:
        if last_reminder_at.tzinfo is None:
            last_reminder_at = last_reminder_at.replace(tzinfo=timezone.utc)
        if now - last_reminder_at < timedelta(hours=24):
            if invoice.last_reminder_status == "sent":
                return {
                    "status": "already_sent",
                    "sent_at": invoice.last_reminder_at.isoformat(),
                }
            raise HTTPException(
                status_code=409,
                detail="A reminder was already attempted recently and will not be resent to avoid duplicates.",
            )

    invoice.last_reminder_at = now
    invoice.last_reminder_status = "pending"
    db.add(
        AuditLog(
            agreement_id=agreement.id,
            user_id=current_user.id,
            action="invoice_payment_reminder_requested",
            entity_type="invoice",
            entity_id=invoice.id,
            details='{"provider":"paypal_sandbox"}',
        )
    )
    db.commit()
    try:
        paypal.send_invoice_reminder(invoice.paypal_invoice_id)
    except PaypalAPIError as exc:
        invoice.last_reminder_status = "failed"
        db.add(
            AuditLog(
                agreement_id=agreement.id,
                user_id=current_user.id,
                action="invoice_payment_reminder_failed",
                entity_type="invoice",
                entity_id=invoice.id,
                details=json.dumps(
                    {
                        "status_code": exc.status_code,
                        "error_name": exc.error_name,
                        "debug_id": exc.debug_id,
                    },
                    separators=(",", ":"),
                ),
            )
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail="PayPal Sandbox could not send the payment reminder. It will not be retried automatically.",
        ) from exc

    invoice.last_reminder_status = "sent"
    db.add(
        AuditLog(
            agreement_id=agreement.id,
            user_id=current_user.id,
            action="invoice_payment_reminder_sent",
            entity_type="invoice",
            entity_id=invoice.id,
            details='{"provider":"paypal_sandbox"}',
        )
    )
    db.commit()
    return {"status": "sent", "sent_at": now.isoformat()}


@router.post("/invoices/{invoice_id}/simulate-mock-payment", response_model=InvoiceResponse)
def simulate_mock_invoice_payment(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    paypal: PaypalClient | MockPaypalClient = Depends(get_paypal_client),
    settings: Settings = Depends(get_settings),
) -> Invoice:
    if settings.DEMO_MODE != "mock" or not isinstance(paypal, MockPaypalClient):
        raise HTTPException(
            status_code=404,
            detail="Mock payment simulation is available only in explicit mock mode.",
        )
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or not invoice.paypal_invoice_id:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    milestone = db.get(Milestone, invoice.milestone_id)
    agreement = db.get(Agreement, milestone.agreement_id) if milestone else None
    if (
        agreement is None
        or current_user.role != "client"
        or current_user.organization_id != agreement.client_org_id
    ):
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if invoice.status != "SENT":
        raise HTTPException(status_code=409, detail="Only a sent mock invoice can be simulated as paid.")

    try:
        simulated = paypal.simulate_payment(invoice.paypal_invoice_id)
        if (
            simulated.get("id") != invoice.paypal_invoice_id
            or simulated.get("status") != "PAID"
        ):
            raise ValueError("Mock payment simulator returned an unexpected status.")
        apply_paypal_invoice_status(db, invoice, simulated["status"])
        db.add(
            AuditLog(
                agreement_id=agreement.id,
                user_id=current_user.id,
                action="mock_payment_simulated",
                entity_type="invoice",
                entity_id=invoice.id,
                details='{"source":"explicit_mock_simulation","status":"PAID"}',
            )
        )
        db.commit()
        db.refresh(invoice)
        return invoice
    except (InvalidTransitionError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
