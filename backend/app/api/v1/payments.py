from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_paypal_client
from app.models.approval import Approval
from app.models.agreement import Agreement
from app.models.audit import AuditLog
from app.models.invoice import Invoice
from app.models.milestone import Milestone
from app.models.user import User
from app.services.paypal.client import PaypalAPIError, PaypalClient
from app.services.paypal.invoicing import (
    apply_paypal_invoice_status,
    create_or_retry_invoice,
    log_invoice_operation_failure,
    redacted_invoice_error_message,
)
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
        db.add(
            AuditLog(
                agreement_id=agreement.id,
                user_id=current_user.id,
                action="invoice_status_synchronized",
                entity_type="invoice",
                entity_id=invoice.id,
                details='{"source":"paypal_api"}',
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
