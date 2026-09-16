from django.core.exceptions import ValidationError


def can_submit(request):
    if not request.partner_id:
        raise ValidationError("Partner is required.")

    if not request.service:
        raise ValidationError("Service is required.")

    if not request.direction:
        raise ValidationError("Direction is required.")

    if not request.target_date:
        raise ValidationError("Target date is required.")

    return True


def owner_assigned(request):
    if not request.owner_id:
        raise ValidationError("An owner must be assigned before testing.")

    return True

def testing_checklist_complete(request):
    incomplete_items = request.checklist_items.filter(
        step="TESTING",
        required=True,
    ).exclude(
        status__in=["DONE", "NOT_APPLICABLE"]
    )

    if incomplete_items.exists():
        raise ValidationError(
            "All required Testing checklist items must be completed."
        )

    return True

def approval_checklist_complete(request):
    incomplete_items = request.checklist_items.filter(
        step="APPROVAL",
        required=True,
    ).exclude(
        status__in=["DONE", "NOT_APPLICABLE"]
    )

    if incomplete_items.exists():
        raise ValidationError(
            "All required Approval checklist items must be completed."
        )

    if not request.comments.exists():
        raise ValidationError(
            "A comment is required before moving to Deployment."
        )

    return True

def deployment_checklist_complete(request):
    incomplete_items = request.checklist_items.filter(
        step="DEPLOYMENT",
        required=True,
    ).exclude(
        status__in=["DONE", "NOT_APPLICABLE"]
    )

    if incomplete_items.exists():
        raise ValidationError(
            "All required Deployment checklist items must be completed."
        )

    if not request.actual_go_live_date:
        raise ValidationError(
            "Actual go-live date is required before moving to Live."
        )

    return True

def valid_rejection_reason(request):
    # §4 requires "a reason of at least 20 characters." Checking just
    # request.comments.exists() (the old version) accepted a 1-character
    # comment — this checks the length of the MOST RECENT comment, which
    # is the one views.py writes right before calling this transition.
    last_comment = request.comments.order_by("-timestamp").first()

    if not last_comment or len(last_comment.text.strip()) < 20:
        raise ValidationError(
            "A rejection reason of at least 20 characters is required."
        )

    return True


def valid_hold_reason(request):
    if not request.on_hold_reason.strip():
        raise ValidationError(
            "A reason is required when putting a request on hold."
        )

    return True