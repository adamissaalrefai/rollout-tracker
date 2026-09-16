from django.core.exceptions import ValidationError
from django.utils import timezone

from .transitions import TRANSITIONS
from .history import log_step_change

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

# Steps that have checklist templates behind them — entering one of these
# copies that service's template items onto the request as real rows
# (§3), so the request owns its own copy from that point on.
STEPS_WITH_CHECKLISTS = {"TESTING", "APPROVAL", "DEPLOYMENT"}


def check_role(actor, allowed_roles):
    if not actor.is_authenticated:
        raise ValidationError("You must be authenticated to perform this transition.")

    if not actor.groups.filter(name__in=allowed_roles).exists():
        raise ValidationError(
            f"You are not allowed to perform this transition. "
            f"Required role: {', '.join(allowed_roles)}."
        )


def check_version(request, expected_version):
    """
    Two-people-editing protection (§6c), applied to transitions. If the
    caller supplied the version they saw when they loaded the page, and
    it doesn't match what's actually in the database right now, someone
    else changed this request in between — refuse instead of silently
    overwriting whatever they did.
    """
    if expected_version is None:
        return  # caller didn't opt in to the check (e.g. internal/seed usage)

    from core.models import Request
    current = Request.objects.get(pk=request.pk).version

    if current != expected_version:
        raise ValidationError(
            "This request changed while you were looking at it, please reload."
        )


def copy_checklist_templates(request, step):
    """
    §3: "When a request enters a step, the app copies that step's
    template items onto the request as real rows." Only copies if this
    request doesn't already have items for this step, so re-entering a
    step (e.g. after being rejected and somehow reopened, or a resume)
    never duplicates rows or overwrites progress already made.
    """
    from core.models import ChecklistTemplateItem, ChecklistItem

    if request.checklist_items.filter(step=step).exists():
        return

    templates = ChecklistTemplateItem.objects.filter(service=request.service, step=step)
    for t in templates:
        ChecklistItem.objects.create(
            request=request, step=step, label=t.label, required=t.required,
        )


def perform_transition(request, target_step, actor, reason=None, expected_version=None):
    check_version(request, expected_version)

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

        resumed_reason = request.on_hold_reason

        request.current_step = target_step
        request.on_hold_from_step = None
        request.on_hold_reason = ""
        request.step_entered_at = timezone.now()
        request.version += 1
        request.save(
            update_fields=[
                "current_step", "on_hold_from_step", "on_hold_reason",
                "step_entered_at", "version",
            ]
        )

        log_step_change(
            request=request, actor=actor, from_step="ON_HOLD",
            to_step=target_step, comment=f"Resumed (was on hold: {resumed_reason})",
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

    history_comment = ""

    if target_step == "ON_HOLD":
        if not reason or not reason.strip():
            raise ValidationError(
                "A reason is required when putting a request on hold."
            )
        request.on_hold_from_step = current_step
        request.on_hold_reason = reason.strip()
        history_comment = reason.strip()

    else:
        condition_name = transition.get("condition")
        if condition_name:
            condition = CONDITIONS[condition_name]
            condition(request)

        if reason:
            history_comment = reason.strip()

    request.current_step = target_step
    request.step_entered_at = timezone.now()
    request.version += 1

    request.save(
        update_fields=[
            "current_step", "on_hold_from_step", "on_hold_reason",
            "step_entered_at", "version",
        ]
    )

    # Copy checklist templates onto the request AFTER the step change is
    # saved, so the request definitely reflects the step it's now in.
    if target_step in STEPS_WITH_CHECKLISTS:
        copy_checklist_templates(request, target_step)

# trying to push again to github
    log_step_change(
        request=request, actor=actor, from_step=current_step,
        to_step=target_step, comment=history_comment,
    )

    return request
