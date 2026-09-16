from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from core.models import Request


class AppendOnlyQuerySet(models.QuerySet):
    """
    Blocks bulk updates and deletes at the queryset level, so things like
    HistoryEntry.objects.filter(...).delete() or .update() are refused
    too — not just single-object saves. §6b calls for the log to be
    append-only, and "append-only" has to hold for bulk operations as
    well or the protection is trivially bypassable.
    """

    def update(self, *args, **kwargs):
        raise ValidationError("History entries are append-only and cannot be updated.")

    def delete(self, *args, **kwargs):
        raise ValidationError("History entries are append-only and cannot be deleted.")


class HistoryEntry(models.Model):
    """
    An append-only log row: one row per meaningful action on a Request
    (a step move, an owner change, a checklist tick, a field edit).

    APPEND-ONLY ENFORCEMENT (§6b): once a row is created it can never be
    updated or deleted. save() refuses any call on a row that already
    has a pk, delete() always refuses, and the custom queryset above
    blocks the bulk versions of both.
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

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["timestamp"]
        verbose_name_plural = "History entries"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("History entries are append-only and cannot be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("History entries are append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.timestamp} - {self.action} on {self.request}"