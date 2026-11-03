class InvalidTransitionError(Exception):
    def __init__(self, entity: str, current_state: str, target_state: str, reason: str = ""):
        self.entity = entity
        self.current_state = current_state
        self.target_state = target_state
        self.reason = reason
        msg = f"{entity}: cannot transition from {current_state} to {target_state}"
        if reason:
            msg += f" — {reason}"
        super().__init__(msg)


class RoleError(Exception):
    def __init__(self, required_role: str, actual_role: str):
        super().__init__(f"Required role: {required_role}, got: {actual_role}")


class SequentialMilestoneError(Exception):
    def __init__(self, milestone_order: int):
        super().__init__(f"Milestone {milestone_order} cannot start: previous milestone not yet PAID")
