from django.core.exceptions import ValidationError

from .transitions import TRANSITIONS

from .conditions import (
    can_submit,
    deployment_checklist_complete,
    owner_assigned,
    testing_checklist_complete,
    approval_checklist_complete,
    valid_rejection_reason,
    valid_hold_reason,
)

CONDITIONS = {
    "can_submit": can_submit,
    "owner_assigned": owner_assigned,
    "testing_checklist_complete": testing_checklist_complete,
    "approval_checklist_complete": approval_checklist_complete,
    "deployment_checklist_complete": deployment_checklist_complete,
    "valid_rejection_reason": valid_rejection_reason,
    "valid_hold_reason": valid_hold_reason,
}

def check_role(actor, allowed_roles):
    if not actor.is_authenticated:
        raise ValidationError("You must be authenticated to perform this transition.")

    if not actor.groups.filter(name__in=allowed_roles).exists():
        raise ValidationError(
            f"You are not allowed to perform this transition. "
            f"Required role: {', '.join(allowed_roles)}."
        )


def perform_transition(request, target_step, actor, reason=None):
    current_step = request.current_step

    # Resuming from On Hold
    if current_step == "ON_HOLD":
        check_role(actor, ["Coordinator"])

        if not request.on_hold_from_step:
            raise ValidationError(
                "Cannot resume a request without a previous step."
            )

        if target_step != request.on_hold_from_step:
            raise ValidationError(
                f"Request must resume to {request.on_hold_from_step}."
            )

        request.current_step = target_step
        request.on_hold_from_step = None
        request.on_hold_reason = ""
        request.save(
            update_fields=[
                "current_step",
                "on_hold_from_step",
                "on_hold_reason",
            ]
        )

        return request

    # Normal transition
    transition = TRANSITIONS.get((current_step, target_step))

    if transition is None:
        raise ValidationError(
            f"Invalid transition from {current_step} to {target_step}."
        )

    allowed_roles = transition.get("allowed_roles", [])

    check_role(actor, allowed_roles)

    # Moving into On Hold
    if target_step == "ON_HOLD":
      if not reason or not reason.strip():
        raise ValidationError(
            "A reason is required when putting a request on hold."
        )

      request.on_hold_from_step = current_step
      request.on_hold_reason = reason.strip()

    else:
      condition_name = transition.get("condition")

      if condition_name:
        condition = CONDITIONS[condition_name]
        condition(request)

    request.current_step = target_step

    request.save(
        update_fields=[
            "current_step",
            "on_hold_from_step",
            "on_hold_reason",
        ]
    )

    return request