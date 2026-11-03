import pytest
from app.state_machine.agreement_fsm import (
    AgreementStatus,
    validate_agreement_transition,
    get_allowed_transitions as get_agreement_transitions,
)
from app.state_machine.milestone_fsm import (
    MilestoneStatus,
    validate_milestone_transition,
    get_allowed_transitions as get_milestone_transitions,
)
from app.state_machine.exceptions import (
    InvalidTransitionError,
    RoleError,
    SequentialMilestoneError,
)


# ──────────────────────────────────────────────
# Agreement FSM Tests
# ──────────────────────────────────────────────


def _make_milestones(count=1, amount_cents=1000, criteria_count=1, status="PENDING"):
    """Helper to build milestone dicts for agreement FSM validation."""
    return [
        {
            "title": f"Milestone {i+1}",
            "amount_cents": amount_cents,
            "criteria_count": criteria_count,
            "status": status,
        }
        for i in range(count)
    ]


def test_draft_to_proposed_valid():
    milestones = _make_milestones(count=2, amount_cents=500, criteria_count=2)
    validate_agreement_transition(
        current=AgreementStatus.DRAFT,
        target=AgreementStatus.PROPOSED,
        user_role="client",
        milestones=milestones,
        total_amount_cents=1000,
    )


def test_draft_to_proposed_no_milestones():
    with pytest.raises(InvalidTransitionError, match="at least 1 milestone required"):
        validate_agreement_transition(
            current=AgreementStatus.DRAFT,
            target=AgreementStatus.PROPOSED,
            user_role="client",
            milestones=[],
            total_amount_cents=1000,
        )


def test_draft_to_proposed_sum_mismatch():
    milestones = _make_milestones(count=1, amount_cents=500, criteria_count=1)
    with pytest.raises(InvalidTransitionError, match="milestone sum"):
        validate_agreement_transition(
            current=AgreementStatus.DRAFT,
            target=AgreementStatus.PROPOSED,
            user_role="client",
            milestones=milestones,
            total_amount_cents=1000,
        )


def test_draft_to_proposed_missing_criteria():
    milestones = _make_milestones(count=1, amount_cents=1000, criteria_count=0)
    with pytest.raises(InvalidTransitionError, match="at least 1 acceptance criterion"):
        validate_agreement_transition(
            current=AgreementStatus.DRAFT,
            target=AgreementStatus.PROPOSED,
            user_role="client",
            milestones=milestones,
            total_amount_cents=1000,
        )


def test_proposed_to_active_by_provider():
    validate_agreement_transition(
        current=AgreementStatus.PROPOSED,
        target=AgreementStatus.ACTIVE,
        user_role="provider",
    )


def test_proposed_to_active_wrong_role():
    with pytest.raises(RoleError, match="Required role: provider"):
        validate_agreement_transition(
            current=AgreementStatus.PROPOSED,
            target=AgreementStatus.ACTIVE,
            user_role="client",
        )


def test_proposed_to_rejected_by_provider():
    validate_agreement_transition(
        current=AgreementStatus.PROPOSED,
        target=AgreementStatus.REJECTED,
        user_role="provider",
    )


def test_proposed_to_draft_recall_by_client():
    validate_agreement_transition(
        current=AgreementStatus.PROPOSED,
        target=AgreementStatus.DRAFT,
        user_role="client",
    )


def test_active_to_completed_all_paid():
    milestones = _make_milestones(count=3, amount_cents=1000, status="PAID")
    validate_agreement_transition(
        current=AgreementStatus.ACTIVE,
        target=AgreementStatus.COMPLETED,
        user_role=None,
        milestones=milestones,
    )


def test_active_to_completed_not_all_paid():
    milestones = [
        {"title": "M1", "amount_cents": 500, "criteria_count": 1, "status": "PAID"},
        {"title": "M2", "amount_cents": 500, "criteria_count": 1, "status": "IN_PROGRESS"},
    ]
    with pytest.raises(InvalidTransitionError, match="is not PAID"):
        validate_agreement_transition(
            current=AgreementStatus.ACTIVE,
            target=AgreementStatus.COMPLETED,
            user_role=None,
            milestones=milestones,
        )


def test_active_to_completed_no_milestones():
    with pytest.raises(InvalidTransitionError, match="at least 1 milestone required"):
        validate_agreement_transition(
            current=AgreementStatus.ACTIVE,
            target=AgreementStatus.COMPLETED,
            user_role=None,
            milestones=[],
        )


def test_draft_to_cancelled():
    validate_agreement_transition(
        current=AgreementStatus.DRAFT,
        target=AgreementStatus.CANCELLED,
        user_role="client",
    )


def test_active_to_cancelled():
    validate_agreement_transition(
        current=AgreementStatus.ACTIVE,
        target=AgreementStatus.CANCELLED,
        user_role="client",
    )


def test_invalid_agreement_transition():
    with pytest.raises(InvalidTransitionError):
        validate_agreement_transition(
            current=AgreementStatus.DRAFT,
            target=AgreementStatus.ACTIVE,
            user_role="client",
        )


def test_get_allowed_transitions_draft_client():
    allowed = get_agreement_transitions(AgreementStatus.DRAFT, user_role="client")
    assert AgreementStatus.PROPOSED in allowed
    assert AgreementStatus.CANCELLED in allowed
    assert AgreementStatus.ACTIVE not in allowed


def test_get_allowed_transitions_proposed_provider():
    allowed = get_agreement_transitions(AgreementStatus.PROPOSED, user_role="provider")
    assert AgreementStatus.ACTIVE in allowed
    assert AgreementStatus.REJECTED in allowed
    assert AgreementStatus.CANCELLED not in allowed


# ──────────────────────────────────────────────
# Milestone FSM Tests
# ──────────────────────────────────────────────


def test_pending_to_in_progress_first_milestone():
    validate_milestone_transition(
        current=MilestoneStatus.PENDING,
        target=MilestoneStatus.IN_PROGRESS,
        user_role="provider",
        milestone_order=0,
        previous_milestone_status=None,
    )


def test_pending_to_in_progress_sequential_previous_not_paid():
    with pytest.raises(SequentialMilestoneError, match="previous milestone not yet PAID"):
        validate_milestone_transition(
            current=MilestoneStatus.PENDING,
            target=MilestoneStatus.IN_PROGRESS,
            user_role="provider",
            milestone_order=1,
            previous_milestone_status="IN_PROGRESS",
        )


def test_pending_to_in_progress_sequential_previous_paid():
    validate_milestone_transition(
        current=MilestoneStatus.PENDING,
        target=MilestoneStatus.IN_PROGRESS,
        user_role="provider",
        milestone_order=1,
        previous_milestone_status="PAID",
    )


def test_in_progress_to_in_review_with_evidence():
    validate_milestone_transition(
        current=MilestoneStatus.IN_PROGRESS,
        target=MilestoneStatus.IN_REVIEW,
        user_role="provider",
        evidence_count=3,
    )


def test_in_progress_to_in_review_no_evidence():
    with pytest.raises(InvalidTransitionError, match="at least 1 evidence item required"):
        validate_milestone_transition(
            current=MilestoneStatus.IN_PROGRESS,
            target=MilestoneStatus.IN_REVIEW,
            user_role="provider",
            evidence_count=0,
        )


def test_in_review_to_approved_by_client():
    validate_milestone_transition(
        current=MilestoneStatus.IN_REVIEW,
        target=MilestoneStatus.APPROVED,
        user_role="client",
    )


def test_in_review_to_approved_wrong_role():
    with pytest.raises(RoleError, match="Required role: client"):
        validate_milestone_transition(
            current=MilestoneStatus.IN_REVIEW,
            target=MilestoneStatus.APPROVED,
            user_role="provider",
        )


def test_in_review_to_revision_requested():
    validate_milestone_transition(
        current=MilestoneStatus.IN_REVIEW,
        target=MilestoneStatus.REVISION_REQUESTED,
        user_role="client",
    )


def test_revision_requested_to_in_progress():
    validate_milestone_transition(
        current=MilestoneStatus.REVISION_REQUESTED,
        target=MilestoneStatus.IN_PROGRESS,
        user_role="provider",
    )


def test_approved_to_invoicing_system():
    validate_milestone_transition(
        current=MilestoneStatus.APPROVED,
        target=MilestoneStatus.INVOICING,
        user_role=None,
    )


def test_invoicing_to_payment_pending():
    validate_milestone_transition(
        current=MilestoneStatus.INVOICING,
        target=MilestoneStatus.PAYMENT_PENDING,
        user_role=None,
    )


def test_invoice_creation_failure_returns_to_approved_for_retry():
    validate_milestone_transition(
        current=MilestoneStatus.INVOICING,
        target=MilestoneStatus.APPROVED,
        user_role=None,
    )


def test_payment_pending_to_paid():
    validate_milestone_transition(
        current=MilestoneStatus.PAYMENT_PENDING,
        target=MilestoneStatus.PAID,
        user_role=None,
    )


def test_payment_pending_to_invoice_cancelled():
    validate_milestone_transition(
        current=MilestoneStatus.PAYMENT_PENDING,
        target=MilestoneStatus.INVOICE_CANCELLED,
        user_role=None,
    )


def test_payment_pending_to_invoice_expired():
    validate_milestone_transition(
        current=MilestoneStatus.PAYMENT_PENDING,
        target=MilestoneStatus.INVOICE_EXPIRED,
        user_role=None,
    )


def test_invoice_cancelled_to_invoicing_retry():
    validate_milestone_transition(
        current=MilestoneStatus.INVOICE_CANCELLED,
        target=MilestoneStatus.INVOICING,
        user_role=None,
    )


def test_invoice_expired_to_invoicing_retry():
    validate_milestone_transition(
        current=MilestoneStatus.INVOICE_EXPIRED,
        target=MilestoneStatus.INVOICING,
        user_role=None,
    )


def test_invalid_milestone_transition():
    with pytest.raises(InvalidTransitionError):
        validate_milestone_transition(
            current=MilestoneStatus.PENDING,
            target=MilestoneStatus.APPROVED,
            user_role="client",
        )


def test_get_allowed_transitions_in_review_client():
    allowed = get_milestone_transitions(MilestoneStatus.IN_REVIEW, user_role="client")
    assert MilestoneStatus.REVISION_REQUESTED in allowed
    assert MilestoneStatus.APPROVED in allowed
    assert MilestoneStatus.IN_PROGRESS not in allowed
