from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import Agreement, Approval, AuditLog, Evidence, Invoice, Milestone, User
from app.state_machine.agreement_fsm import AgreementStatus
from app.state_machine.milestone_fsm import MilestoneStatus

_INVOICE_ELIGIBLE_STATUSES = {
    MilestoneStatus.APPROVED.value,
    MilestoneStatus.INVOICING.value,
    MilestoneStatus.INVOICE_CANCELLED.value,
    MilestoneStatus.INVOICE_EXPIRED.value,
}
_REVIEW_SUBMITTED_STATUSES = {
    MilestoneStatus.IN_REVIEW.value,
    MilestoneStatus.APPROVED.value,
    MilestoneStatus.INVOICING.value,
    MilestoneStatus.PAYMENT_PENDING.value,
    MilestoneStatus.PAID.value,
    MilestoneStatus.INVOICE_CANCELLED.value,
    MilestoneStatus.INVOICE_EXPIRED.value,
}


class PaymentNotReadyError(ValueError):
    def __init__(self, readiness: dict[str, Any]) -> None:
        self.readiness = readiness
        reasons = readiness["blocking_reasons"]
        super().__init__(" ".join(reasons) or "The milestone is not eligible for invoicing.")


def _deadline_defined(agreement: Agreement | None) -> bool:
    if agreement is None or not agreement.description:
        return False
    try:
        description = json.loads(agreement.description)
    except json.JSONDecodeError:
        return False
    deadline = description.get("deadline") if isinstance(description, dict) else None
    return isinstance(deadline, str) and bool(deadline.strip())


def _scope_defined(
    agreement: Agreement | None,
    milestone: Milestone,
    criteria_defined: bool,
) -> bool:
    if agreement is None or not agreement.title.strip():
        return False
    try:
        description = json.loads(agreement.description or "{}")
    except json.JSONDecodeError:
        description = {}
    requirements = description.get("requirements") if isinstance(description, dict) else None
    return bool(
        (
            isinstance(requirements, list)
            and any(isinstance(item, str) and item.strip() for item in requirements)
        )
        or (isinstance(milestone.description, str) and milestone.description.strip())
        or criteria_defined
    )


def calculate_payment_readiness(
    db: Session,
    milestone: Milestone,
) -> dict[str, Any]:
    agreement = db.get(Agreement, milestone.agreement_id)
    criteria = sorted(milestone.criteria, key=lambda criterion: criterion.id)
    evidence = (
        db.query(Evidence)
        .filter(Evidence.milestone_id == milestone.id)
        .order_by(Evidence.created_at.desc(), Evidence.id.desc())
        .all()
    )
    latest_evidence = evidence[0] if evidence else None
    report: dict[str, Any] = {}
    advisory_verdict = "unavailable"
    if latest_evidence and latest_evidence.ai_report:
        try:
            parsed_report = json.loads(latest_evidence.ai_report)
        except json.JSONDecodeError:
            parsed_report = None
        if isinstance(parsed_report, dict):
            report = parsed_report
        report_verdict = report.get("overall_verdict")
        if report_verdict in {"sufficient", "partial", "insufficient"}:
            advisory_verdict = report_verdict

    raw_results = report.get("criteria_results")
    results_by_criterion = {
        item.get("criterion"): item.get("status")
        for item in raw_results
        if isinstance(item, dict)
        and isinstance(item.get("criterion"), str)
        and item.get("status") in {"verified", "not_verifiable", "missing"}
    } if isinstance(raw_results, list) else {}
    criteria_results = [
        {
            "criterion": criterion.description,
            "status": results_by_criterion.get(criterion.description, "missing"),
        }
        for criterion in criteria
    ]
    verified_count = sum(item["status"] == "verified" for item in criteria_results)
    unverified_count = len(criteria_results) - verified_count
    review_complete = (
        bool(criteria_results)
        and all(
            criterion.description in results_by_criterion
            for criterion in criteria
        )
        and all(item["status"] in {"verified", "not_verifiable", "missing"} for item in criteria_results)
    )
    criteria_satisfied = (
        bool(criteria_results)
        and review_complete
        and all(item["status"] == "verified" for item in criteria_results)
    )

    latest_approval = (
        db.query(Approval, User)
        .join(User, Approval.approved_by == User.id)
        .filter(Approval.milestone_id == milestone.id)
        .order_by(Approval.created_at.desc(), Approval.id.desc())
        .first()
    )
    approval_status = "PENDING"
    human_approved = False
    client_acknowledged_unverified = False
    approval_details = None
    if latest_approval:
        approval, approver = latest_approval
        try:
            approval_notes = json.loads(approval.notes or "{}")
        except json.JSONDecodeError:
            approval_notes = {}
        if approval.decision == "rejected":
            approval_status = "REJECTED"
        elif (
            approval.decision == "approved"
            and agreement is not None
            and approver.role == "client"
            and approver.organization_id == agreement.client_org_id
        ):
            approval_status = "APPROVED"
            human_approved = True
            client_acknowledged_unverified = (
                isinstance(approval_notes, dict)
                and approval_notes.get("acknowledged_unverified") is True
            )
            approval_details = {
                "approver_name": approver.name,
                "approved_at": approval.created_at.isoformat()
                if approval.created_at
                else None,
                "advisory_overridden": client_acknowledged_unverified,
            }

    invoice = (
        db.query(Invoice)
        .filter(Invoice.milestone_id == milestone.id)
        .order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .first()
    )
    paypal_status = invoice.status if invoice else "NOT_CREATED"
    webhook_payment_confirmed = False
    if invoice is not None:
        paid_webhook = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_type == "invoice",
                AuditLog.entity_id == invoice.id,
                AuditLog.action == "paypal_invoice_status_updated",
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .first()
        )
        if paid_webhook:
            try:
                webhook_details = json.loads(paid_webhook.details or "{}")
            except json.JSONDecodeError:
                webhook_details = {}
            webhook_payment_confirmed = (
                isinstance(webhook_details, dict)
                and webhook_details.get("status") == "PAID"
            )
    payment_confirmed = (
        milestone.status == MilestoneStatus.PAID.value
        or paypal_status == "PAID"
    )
    agreement_valid = bool(
        agreement
        and (
            agreement.status == AgreementStatus.ACTIVE.value
            or (
                payment_confirmed
                and agreement.status == AgreementStatus.COMPLETED.value
            )
        )
    )
    amount_defined = milestone.amount_cents > 0
    criteria_defined = bool(criteria) and all(
        criterion.description.strip() for criterion in criteria
    )
    scope_defined = _scope_defined(agreement, milestone, criteria_defined)
    review_submitted = milestone.status in _REVIEW_SUBMITTED_STATUSES
    next_milestone = (
        db.query(Milestone)
        .filter(
            Milestone.agreement_id == milestone.agreement_id,
            Milestone.order > milestone.order,
        )
        .order_by(Milestone.order.asc())
        .first()
    )
    next_milestone_unlocked = (
        next_milestone is None
        or next_milestone.status != MilestoneStatus.PENDING.value
    )

    checks = [
        {"key": "agreement_valid", "label": "Active work agreement", "complete": agreement_valid, "required": True},
        {"key": "amount_defined", "label": "Milestone amount defined", "complete": amount_defined, "required": True},
        {"key": "deadline_defined", "label": "Project deadline defined", "complete": _deadline_defined(agreement), "required": False},
        {"key": "criteria_defined", "label": "Acceptance criteria defined", "complete": criteria_defined, "required": True},
        {"key": "evidence_submitted", "label": "Evidence submitted", "complete": bool(evidence), "required": True},
        {"key": "evidence_reviewed", "label": "AI evidence review completed", "complete": review_complete, "required": True},
        {"key": "criteria_satisfied", "label": "All acceptance criteria verified", "complete": criteria_satisfied, "required": True},
        {"key": "submitted_for_review", "label": "Submitted for client review", "complete": review_submitted, "required": True},
        {"key": "human_approved", "label": "Client approval recorded", "complete": human_approved, "required": True},
        {"key": "paypal_invoice_allowed", "label": "PayPal invoice can be created", "complete": False, "required": False},
        {"key": "payment_confirmed", "label": "Payment confirmed by PayPal", "complete": payment_confirmed, "required": False},
    ]

    criteria_gate_satisfied = criteria_satisfied or client_acknowledged_unverified
    review_gate_satisfied = review_complete or client_acknowledged_unverified
    requirements_satisfied = (
        agreement_valid
        and amount_defined
        and criteria_defined
        and bool(evidence)
        and review_gate_satisfied
        and criteria_gate_satisfied
        and review_submitted
    )
    client_approval_allowed = (
        agreement_valid
        and amount_defined
        and criteria_defined
        and bool(evidence)
        and review_submitted
        and milestone.status == MilestoneStatus.IN_REVIEW.value
    )
    blocking_reasons: list[str] = []
    if not agreement_valid:
        blocking_reasons.append("The agreement must be active.")
    if not amount_defined:
        blocking_reasons.append("The milestone amount must be greater than zero.")
    if not criteria_defined:
        blocking_reasons.append("Acceptance criteria are missing.")
    if not evidence:
        blocking_reasons.append("Evidence has not been submitted.")
    elif not review_complete and not client_acknowledged_unverified:
        blocking_reasons.append("Evidence review is incomplete or unavailable.")
    elif not criteria_satisfied and not client_acknowledged_unverified:
        blocking_reasons.append(f"{unverified_count} acceptance criteria remain unverified.")
    if criteria_satisfied and not review_submitted:
        blocking_reasons.append("Evidence must be submitted for client review.")
    if not human_approved:
        blocking_reasons.append("Client approval is required.")

    invoice_allowed = (
        requirements_satisfied
        and human_approved
        and milestone.status in _INVOICE_ELIGIBLE_STATUSES
        and paypal_status not in {"SENT", "PAID"}
    )
    next(check for check in checks if check["key"] == "paypal_invoice_allowed")[
        "complete"
    ] = invoice_allowed
    if requirements_satisfied and human_approved and not invoice_allowed and not payment_confirmed and paypal_status != "SENT":
        blocking_reasons.append("The milestone is not in an invoice-eligible state.")

    required_checks = [check for check in checks if check["required"]]
    score = round(
        100 * sum(check["complete"] for check in required_checks) / len(required_checks)
    )
    completed_checks = [
        check["label"] for check in required_checks if check["complete"]
    ]

    if payment_confirmed:
        status = "PAID"
    elif paypal_status == "SENT" or milestone.status == MilestoneStatus.PAYMENT_PENDING.value:
        status = "INVOICE_SENT"
    elif paypal_status == "DRAFT" and invoice and invoice.paypal_invoice_id:
        status = "INVOICE_CREATED"
    elif invoice_allowed:
        status = "READY_FOR_PAYMENT"
    elif (client_approval_allowed or requirements_satisfied) and not human_approved:
        status = "READY_FOR_APPROVAL"
    elif requirements_satisfied:
        status = "BLOCKED"
    elif (
        milestone.status == MilestoneStatus.IN_REVIEW.value
        and evidence
        and not review_complete
    ):
        status = "IN_REVIEW"
    elif not agreement_valid:
        status = "NOT_READY"
    else:
        status = "BLOCKED"

    if status == "PAID":
        next_action = {"actor": "SYSTEM", "action": "No action required."}
    elif status == "INVOICE_SENT":
        next_action = {"actor": "CLIENT", "action": "Pay the PayPal invoice."}
    elif status == "INVOICE_CREATED":
        next_action = {"actor": "CLIENT", "action": "Send the PayPal invoice."}
    elif not agreement_valid:
        next_action = {"actor": "CLIENT", "action": "Activate the work agreement."}
    elif not criteria_defined or not amount_defined:
        next_action = {"actor": "CLIENT", "action": "Complete the milestone agreement details."}
    elif not evidence:
        next_action = {"actor": "PROVIDER", "action": "Submit evidence for this milestone."}
    elif client_approval_allowed and not human_approved:
        next_action = {
            "actor": "CLIENT",
            "action": (
                "Review the evidence; approve with acknowledgement if you accept "
                "the advisory limitations, or request a revision."
            ),
        }
    elif not review_complete:
        next_action = {"actor": "AI", "action": "Complete the evidence review."}
    elif not criteria_satisfied:
        next_action = {"actor": "PROVIDER", "action": "Submit evidence for the remaining acceptance criteria."}
    elif not review_submitted:
        next_action = {"actor": "PROVIDER", "action": "Submit the milestone for client review."}
    elif not human_approved:
        next_action = {"actor": "CLIENT", "action": "Review the evidence and approve the milestone."}
    elif invoice_allowed:
        next_action = {"actor": "CLIENT", "action": "Create or retry the PayPal invoice."}
    else:
        next_action = {"actor": "SYSTEM", "action": "Resolve the milestone state before invoicing."}

    client_next_action = next_action["action"]
    if status == "READY_FOR_APPROVAL":
        client_next_action = "Review the evidence, then approve the milestone or request a revision."
    elif status == "BLOCKED" and not evidence:
        client_next_action = "Wait for the provider to submit evidence for this milestone."
    provider_next_action = next_action["action"]
    if status == "READY_FOR_APPROVAL":
        provider_next_action = "Evidence is submitted; wait for the client to review and decide."
    elif status == "READY_FOR_PAYMENT":
        provider_next_action = "Client approval is recorded; wait for the client to create the PayPal invoice."
    elif status == "INVOICE_SENT":
        provider_next_action = "The invoice is sent; wait for the client to complete payment."
    elif status == "PAID":
        provider_next_action = (
            f"Payment is complete; {next_milestone.title} is unlocked."
            if next_milestone
            else "All milestones are paid; the agreement is complete."
        )
    elif evidence and not criteria_satisfied and not client_acknowledged_unverified:
        missing_criteria = [
            item["criterion"]
            for item in criteria_results
            if item["status"] != "verified"
        ]
        provider_next_action = (
            "Submit additional evidence for: " + "; ".join(missing_criteria)
            if missing_criteria
            else "Submit additional evidence for the acceptance criteria."
        )

    return {
        "status": status,
        "score": score,
        "ready": (
            requirements_satisfied
            and human_approved
            and (invoice_allowed or paypal_status in {"SENT", "PAID"})
        ),
        "paypal_invoice_allowed": invoice_allowed,
        "client_approval_allowed": client_approval_allowed,
        "client_acknowledged_advisory": client_acknowledged_unverified,
        "advisory_verdict": advisory_verdict,
        "blocking_reasons": blocking_reasons,
        "completed_checks": completed_checks,
        "checks": checks,
        "next_action": next_action,
        "criteria_summary": {
            "total": len(criteria_results),
            "verified": verified_count,
            "unverified": unverified_count,
            "criteria": criteria_results,
        },
        "approval_status": approval_status,
        "approval_details": approval_details,
        "paypal_status": paypal_status,
        "webhook_payment_confirmed": webhook_payment_confirmed,
        "scope_defined": scope_defined,
        "next_milestone_title": next_milestone.title if next_milestone else None,
        "next_milestone_unlocked": next_milestone_unlocked,
        "client_next_action": client_next_action,
        "provider_next_action": provider_next_action,
    }


def require_payment_readiness(db: Session, milestone: Milestone) -> dict[str, Any]:
    readiness = calculate_payment_readiness(db, milestone)
    if not readiness["ready"] or not readiness["paypal_invoice_allowed"]:
        raise PaymentNotReadyError(readiness)
    return readiness
