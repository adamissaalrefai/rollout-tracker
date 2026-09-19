from django import forms
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Request, Comment, Attachment


class RequestForm(forms.ModelForm):
    """
    The create/edit form for a Request. Covers the fields a Requester
    fills in when starting a new rollout request (§5.3), plus the two
    validation rules the spec requires:
      1. target_date cannot be in the past
      2. the same partner + service + direction cannot have two
         unfinished requests open at the same time

    Also carries a hidden 'version' field, used by request_edit() in
    views.py for the two-people-editing protection from §6c — see the
    view for how the actual conflict check happens.
    """

    version = forms.IntegerField(widget=forms.HiddenInput())

    class Meta:
        model = Request
        fields = [
            "partner",
            "service",
            "direction",
            "owner",
            "priority",
            "target_date",
            "description",
        ]
        widgets = {
            "target_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-fill the hidden version field with whatever version was
        # loaded when the page was rendered — this is the value the view
        # compares against the database's CURRENT version on save, to
        # detect if someone else changed the request in between.
        if self.instance and self.instance.pk:
            self.fields["version"].initial = self.instance.version
        else:
            self.fields["version"].initial = 1

        # Owners are users with an Engineer or Coordinator role.
        self.fields["owner"].queryset = User.objects.filter(
            groups__name__in=["Engineer", "Coordinator"]
        ).distinct()

    def clean_target_date(self):
        target_date = self.cleaned_data["target_date"]
        if target_date < timezone.now().date():
            raise forms.ValidationError("Target date cannot be in the past.")
        return target_date

    def clean(self):
        # clean() runs after all individual field clean_<field> methods,
        # and is the right place for checks that involve MULTIPLE fields
        # together — here, the combination of partner + service + direction.
        cleaned_data = super().clean()

        partner = cleaned_data.get("partner")
        service = cleaned_data.get("service")
        direction = cleaned_data.get("direction")

        if partner and service and direction:
            unfinished = Request.objects.filter(
                partner=partner,
                service=service,
                direction=direction,
            ).exclude(current_step__in=["LIVE", "REJECTED"])

            # When editing an existing request, exclude itself from the
            # check — otherwise every edit would incorrectly flag itself
            # as a "duplicate" of itself.
            if self.instance.pk:
                unfinished = unfinished.exclude(pk=self.instance.pk)

            if unfinished.exists():
                raise forms.ValidationError(
                    "This partner already has an unfinished request for "
                    "this service and direction."
                )

        return cleaned_data


class CommentForm(forms.ModelForm):
    """A single comment left on a request. author and request are set in
    the view (from the logged-in user and the URL), not typed by hand."""

    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3, "placeholder": "Add a comment..."}),
        }


class AttachmentForm(forms.ModelForm):
    """A single file upload attached to a request. The model's own
    validate_file_size validator (5MB limit) runs automatically here —
    nothing extra needed in this form for that rule."""

    class Meta:
        model = Attachment
        fields = ["file"]


class CSVImportForm(forms.Form):
    """Just a single file field — the actual row-by-row parsing and
    validation happens in the view (core/views.py), reusing RequestForm
    per row so the import obeys the exact same two rules as manual
    creation (§5.3)."""

    csv_file = forms.FileField(
        help_text="Columns expected: partner_code, service, direction, priority, target_date, description"
    )