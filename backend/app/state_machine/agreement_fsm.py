from enum import Enum
from typing import Optional
from app.state_machine.exceptions import InvalidTransitionError, RoleError


class AgreementStatus(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


# Map: (from_state, to_state) -> required_role (None = system)
AGREEMENT_TRANSITIONS: dict[tuple[AgreementStatus, AgreementStatus], Optional[str]] = {
    (AgreementStatus.DRAFT, AgreementStatus.PROPOSED): "client",
    (AgreementStatus.PROPOSED, AgreementStatus.ACTIVE): "provider",
    (AgreementStatus.PROPOSED, AgreementStatus.REJECTED): "provider",
    (AgreementStatus.PROPOSED, AgreementStatus.DRAFT): "client",
    (AgreementStatus.ACTIVE, AgreementStatus.COMPLETED): None,  # system
    (AgreementStatus.DRAFT, AgreementStatus.CANCELLED): "client",
    (AgreementStatus.PROPOSED, AgreementStatus.CANCELLED): "client",
    (AgreementStatus.ACTIVE, AgreementStatus.CANCELLED): "client",
}


def validate_agreement_transition(
    current: AgreementStatus,
    target: AgreementStatus,
    user_role: Optional[str] = None,
    milestones: Optional[list] = None,
    total_amount_cents: Optional[int] = None,
) -> None:
    """
    Validate that a transition is allowed. Raises InvalidTransitionError or RoleError.
    milestones should be a list of dicts with keys: amount_cents, criteria_count, status.
    """
    key = (current, target)
    if key not in AGREEMENT_TRANSITIONS:
        raise InvalidTransitionError("Agreement", current.value, target.value)

    required_role = AGREEMENT_TRANSITIONS[key]
    if required_role is not None:
        if user_role != required_role:
            raise RoleError(required_role, user_role or "none")

    # Guards for DRAFT -> PROPOSED
    if current == AgreementStatus.DRAFT and target == AgreementStatus.PROPOSED:
        if not milestones or len(milestones) == 0:
            raise InvalidTransitionError("Agreement", current.value, target.value, "at least 1 milestone required")
        total_milestone_cents = sum(m["amount_cents"] for m in milestones)
        if total_amount_cents is not None and total_milestone_cents != total_amount_cents:
            raise InvalidTransitionError(
                "Agreement", current.value, target.value,
                f"milestone sum ({total_milestone_cents}) != agreement total ({total_amount_cents})"
            )
        for m in milestones:
            if m.get("criteria_count", 0) < 1:
                raise InvalidTransitionError(
                    "Agreement", current.value, target.value,
                    f"milestone '{m.get('title', '?')}' must have at least 1 acceptance criterion"
                )

    # Guard for ACTIVE -> COMPLETED: all milestones must be PAID
    if current == AgreementStatus.ACTIVE and target == AgreementStatus.COMPLETED:
        if not milestones:
            raise InvalidTransitionError(
                "Agreement", current.value, target.value, "at least 1 milestone required"
            )
        for m in milestones:
            if m.get("status") != "PAID":
                raise InvalidTransitionError(
                    "Agreement", current.value, target.value,
                    f"milestone '{m.get('title', '?')}' is not PAID"
                )


def get_allowed_transitions(current: AgreementStatus, user_role: Optional[str] = None) -> list[AgreementStatus]:
    """Return list of states reachable from current state for the given role."""
    result = []
    for (from_s, to_s), req_role in AGREEMENT_TRANSITIONS.items():
        if from_s == current:
            if req_role is None or req_role == user_role:
                result.append(to_s)
    return result
