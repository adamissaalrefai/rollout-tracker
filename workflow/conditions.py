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