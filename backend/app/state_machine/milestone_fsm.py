from enum import Enum
from typing import Optional
from app.state_machine.exceptions import InvalidTransitionError, RoleError, SequentialMilestoneError


class MilestoneStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    APPROVED = "APPROVED"
    INVOICING = "INVOICING"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    INVOICE_CANCELLED = "INVOICE_CANCELLED"
    INVOICE_EXPIRED = "INVOICE_EXPIRED"


MILESTONE_TRANSITIONS: dict[tuple[MilestoneStatus, MilestoneStatus], Optional[str]] = {
    (MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS): "provider",
    (MilestoneStatus.IN_PROGRESS, MilestoneStatus.IN_REVIEW): "provider",
    (MilestoneStatus.IN_REVIEW, MilestoneStatus.REVISION_REQUESTED): "client",
    (MilestoneStatus.REVISION_REQUESTED, MilestoneStatus.IN_PROGRESS): "provider",
    (MilestoneStatus.IN_REVIEW, MilestoneStatus.APPROVED): "client",
    (MilestoneStatus.APPROVED, MilestoneStatus.INVOICING): None,  # system
    (MilestoneStatus.INVOICING, MilestoneStatus.PAYMENT_PENDING): None,  # system
    (MilestoneStatus.PAYMENT_PENDING, MilestoneStatus.PAID): None,  # system (webhook)
    (MilestoneStatus.PAYMENT_PENDING, MilestoneStatus.INVOICE_CANCELLED): None,  # system
    (MilestoneStatus.PAYMENT_PENDING, MilestoneStatus.INVOICE_EXPIRED): None,  # system
    (MilestoneStatus.INVOICING, MilestoneStatus.APPROVED): None,  # system (invoice creation failed)
    (MilestoneStatus.INVOICE_CANCELLED, MilestoneStatus.INVOICING): None,  # system retry
    (MilestoneStatus.INVOICE_EXPIRED, MilestoneStatus.INVOICING): None,  # system retry
}


def validate_milestone_transition(
    current: MilestoneStatus,
    target: MilestoneStatus,
    user_role: Optional[str] = None,
    evidence_count: int = 0,
    milestone_order: int = 0,
    previous_milestone_status: Optional[str] = None,
) -> None:
    """Validate milestone state transition with role and business guards."""
    key = (current, target)
    if key not in MILESTONE_TRANSITIONS:
        raise InvalidTransitionError("Milestone", current.value, target.value)

    required_role = MILESTONE_TRANSITIONS[key]
    if required_role is not None:
        if user_role != required_role:
            raise RoleError(required_role, user_role or "none")

    # Guard: sequential milestones (PENDING -> IN_PROGRESS)
    if current == MilestoneStatus.PENDING and target == MilestoneStatus.IN_PROGRESS:
        if milestone_order > 0:  # not the first milestone
            if previous_milestone_status != MilestoneStatus.PAID.value:
                raise SequentialMilestoneError(milestone_order)

    # Guard: must have evidence to submit for review
    if current == MilestoneStatus.IN_PROGRESS and target == MilestoneStatus.IN_REVIEW:
        if evidence_count < 1:
            raise InvalidTransitionError(
                "Milestone", current.value, target.value,
                "at least 1 evidence item required"
            )


def get_allowed_transitions(current: MilestoneStatus, user_role: Optional[str] = None) -> list[MilestoneStatus]:
    """Return list of states reachable from current state for the given role."""
    result = []
    for (from_s, to_s), req_role in MILESTONE_TRANSITIONS.items():
        if from_s == current:
            if req_role is None or req_role == user_role:
                result.append(to_s)
    return result
