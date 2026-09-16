"""
The append-only history log (§6b).

Everything that writes history goes through log_history() here, rather
than creating HistoryEntry rows directly all over the codebase — one
place to change if the log ever needs more fields, and one place to read
if you want to know what actually gets recorded.

The "cannot be faked" part of §6b is enforced on the MODEL itself (see
workflow/models.py): save() refuses to touch an existing row, delete()
always refuses, and bulk update()/delete() are blocked at the queryset
level. So even code that bypasses this module can only ever append.
"""

from .models import HistoryEntry


def log_history(request, actor, action, field_changed="", old_value="", new_value="", comment=""):
    """Writes one history row. Values are coerced to strings so callers
    can pass steps, usernames, dates, or None without worrying."""
    return HistoryEntry.objects.create(
        request=request,
        actor=actor,
        action=action,
        field_changed=field_changed or "",
        old_value="" if old_value is None else str(old_value),
        new_value="" if new_value is None else str(new_value),
        comment=comment or "",
    )


def log_step_change(request, actor, from_step, to_step, comment=""):
    """A request moved from one step to another."""
    return log_history(
        request=request, actor=actor, action="STEP_CHANGE",
        field_changed="current_step", old_value=from_step,
        new_value=to_step, comment=comment,
    )


def log_owner_change(request, actor, old_owner, new_owner):
    """The request's owner was reassigned."""
    return log_history(
        request=request, actor=actor, action="OWNER_CHANGE",
        field_changed="owner",
        old_value=old_owner.username if old_owner else "",
        new_value=new_owner.username if new_owner else "",
    )


def log_checklist_change(request, actor, item_label, old_status, new_status):
    """A checklist item's status was ticked/changed."""
    return log_history(
        request=request, actor=actor, action="CHECKLIST_CHANGE",
        field_changed=item_label, old_value=old_status, new_value=new_status,
    )


def log_field_edit(request, actor, field_name, old_value, new_value):
    """Any other field on the request was edited."""
    return log_history(
        request=request, actor=actor, action="FIELD_EDIT",
        field_changed=field_name, old_value=old_value, new_value=new_value,
    )