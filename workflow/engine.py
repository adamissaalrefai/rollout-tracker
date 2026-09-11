from django.core.exceptions import ValidationError

from .transitions import TRANSITIONS

from .conditions import (
    can_submit,
    owner_assigned,
    testing_checklist_complete,
    approval_checklist_complete,
)

CONDITIONS = {
    "can_submit": can_submit,
    "owner_assigned": owner_assigned,
    "testing_checklist_complete": testing_checklist_complete,
    "approval_checklist_complete": approval_checklist_complete,
}


def perform_transition(request, target_step):
    current_step = request.current_step

    transition = TRANSITIONS.get((current_step, target_step))

    if transition is None:
        raise ValidationError(
            f"Invalid transition from {current_step} to {target_step}."
        )

    condition_name = transition.get("condition")

    if condition_name:
        condition = CONDITIONS[condition_name]
        condition(request)

    request.current_step = target_step
    request.save(update_fields=["current_step"])

    return request