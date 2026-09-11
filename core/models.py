from django.db import models
from django.contrib.auth.models import User


class Partner(models.Model):
    """A company we're doing rollout requests with."""

    REGION_CHOICES = [
        ("EMEA", "EMEA"),
        ("APAC", "APAC"),
        ("AMER", "AMER"),
    ]

    code = models.CharField(max_length=20, unique=True)   # e.g. "PT-DE-001"
    name = models.CharField(max_length=100)                # e.g. "Blue Telecom"
    country = models.CharField(max_length=100)
    region = models.CharField(max_length=10, choices=REGION_CHOICES)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


# The spec lists exactly 5 fixed services with no extra data attached to each
# one (no description, no owner, nothing) — so rather than a whole separate
# table, we store this as a fixed set of choices used on Request and on the
# checklist templates below. This is a design decision, not something forced
# on you — a separate Service model would also work, it's just more table
# for no extra benefit here.
SERVICE_CHOICES = [
    ("VOICE", "Voice"),
    ("SMS", "SMS"),
    ("DATA_4G", "Data 4G"),
    ("DATA_5G", "Data 5G"),
    ("VOLTE", "VoLTE"),
]

STEP_CHOICES = [
    ("DRAFT", "Draft"),
    ("SUBMITTED", "Submitted"),
    ("TESTING", "Testing"),
    ("APPROVAL", "Approval"),
    ("DEPLOYMENT", "Deployment"),
    ("LIVE", "Live"),
    ("REJECTED", "Rejected"),
    ("ON_HOLD", "On Hold"),
]

DIRECTION_CHOICES = [
    ("INBOUND", "Inbound"),
    ("OUTBOUND", "Outbound"),
]


class Request(models.Model):
    """The main object — one rollout request moving through the steps."""

    partner = models.ForeignKey(Partner, on_delete=models.PROTECT)
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    priority = models.CharField(max_length=20, default="NORMAL")
    target_date = models.DateField()
    actual_go_live_date = models.DateField(null=True, blank=True)

    requester = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="requests_created"
    )
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="requests_owned"
    )

    current_step = models.CharField(
        max_length=20, choices=STEP_CHOICES, default="DRAFT"
    )
    description = models.TextField(blank=True)

    # Used for the "two people editing at once" protection (spec section 6c).
    # Every save that changes the request bumps this number by 1.
    version = models.PositiveIntegerField(default=1)

    # When it entered its current step — needed for late detection.
    step_entered_at = models.DateTimeField(auto_now_add=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.partner.code} / {self.service} ({self.current_step})"


class ChecklistTemplateItem(models.Model):
    """
    The reusable template: 'for DATA_5G's Testing step, these are the
    checklist items.' An admin edits these through Django admin.
    When a Request enters a step, its template items get COPIED into real
    ChecklistItem rows below — the request then owns its own copy, so
    editing a template later never changes requests that already passed
    that step.
    """

    service = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    step = models.CharField(max_length=20, choices=STEP_CHOICES)
    label = models.CharField(max_length=200)
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"[{self.service}/{self.step}] {self.label}"


class ChecklistItem(models.Model):
    """
    A real checklist row that belongs to one specific Request. Created by
    copying a ChecklistTemplateItem when the request enters that step.
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("IN_PROGRESS", "In Progress"),
        ("DONE", "Done"),
        ("NOT_APPLICABLE", "Not Applicable"),
    ]

    request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name="checklist_items"
    )
    step = models.CharField(max_length=20, choices=STEP_CHOICES)
    label = models.CharField(max_length=200)
    required = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PENDING"
    )
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    note = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return f"{self.label} ({self.status})"


class Comment(models.Model):
    request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author} on {self.request}"


class Attachment(models.Model):
    request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="attachments/")
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file.name} on {self.request}"