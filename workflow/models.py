from django.db import models
from django.contrib.auth.models import User
from core.models import Request


class HistoryEntry(models.Model):
    """
    An append-only log row: one row per meaningful action on a Request
    (a step move, an owner change, a checklist tick, a field edit).
    This table must NEVER be updated or deleted after creation — that
    rule gets enforced in code later (in workflow/history.py), not here.
    """

    request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name="history"
    )
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)

    action = models.CharField(max_length=100)   # e.g. "STEP_CHANGE", "OWNER_CHANGE"
    field_changed = models.CharField(max_length=100, blank=True)
    old_value = models.CharField(max_length=200, blank=True)
    new_value = models.CharField(max_length=200, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.timestamp} - {self.action} on {self.request}"