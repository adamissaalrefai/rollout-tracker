import csv
import json

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404

from .models import Request, ChecklistItem, Partner
from .forms import RequestForm, CommentForm, AttachmentForm, CSVImportForm
from .filters import RequestFilter
from .csv_export import export_requests_csv  # re-exported here so urls.py has one place to import views from

from workflow.engine import perform_transition, CONDITIONS
from workflow.transitions import TRANSITIONS
from workflow.history import log_checklist_change, log_field_edit
from workflow import steps as S
from .dashboard import (
    get_step_counts,
    get_late_by_region,
    get_average_days_by_step,
    get_go_lives_by_month,
    get_my_open_items,
)

# Which target steps need a typed reason from the user before submitting,
# rather than just a plain "click to confirm" button.
STEPS_NEEDING_REASON = {S.REJECTED, S.ON_HOLD}


def get_available_transitions(req, actor):
    """
    Looks at workflow.transitions.TRANSITIONS and, for every row whose
    FROM step matches this request's current step, dry-checks whether
    `actor` could actually perform it right now — role AND condition —
    without actually making the move. Returns a list of dicts the
    template uses to render each button, each with either "allowed" or
    a human reason it's disabled.

    Built generically off his transitions table, rather than one
    hardcoded button per step, so new rows he adds later show up here
    automatically with no changes needed in this file.
    """
    available = []

    for (from_step, to_step), rule in TRANSITIONS.items():
        if from_step != req.current_step:
            continue

        allowed_roles = rule.get("allowed_roles", [])
        role_ok = actor.groups.filter(name__in=allowed_roles).exists()

        condition_ok = True
        disabled_reason = ""

        if not role_ok:
            condition_ok = False
            disabled_reason = f"Requires role: {', '.join(allowed_roles)}."
        else:
            condition_name = rule.get("condition")
            if condition_name and to_step not in STEPS_NEEDING_REASON:
                condition_fn = CONDITIONS[condition_name]
                try:
                    condition_fn(req)
                except ValidationError as e:
                    condition_ok = False
                    disabled_reason = str(e.message) if hasattr(e, "message") else str(e)

        available.append({
            "target_step": to_step,
            "label": to_step.replace("_", " ").title(),
            "allowed": role_ok and condition_ok,
            "disabled_reason": disabled_reason,
            "needs_reason": to_step in STEPS_NEEDING_REASON,
        })

    # On Hold -> resume isn't in TRANSITIONS at all (handled specially in
    # engine.py, purely based on current_step being ON_HOLD — no special
    # target value needed), so it needs its own separate check here.
    if req.current_step == S.ON_HOLD and req.on_hold_from_step:
        role_ok = actor.groups.filter(name="Coordinator").exists()
        available.append({
            "target_step": req.on_hold_from_step,
            "label": f"Resume to {req.on_hold_from_step.replace('_', ' ').title()}",
            "allowed": role_ok,
            "disabled_reason": "" if role_ok else "Requires role: Coordinator.",
            "needs_reason": False,
        })

    return available


@login_required
def request_list(request):
    """
    The request list screen (§5.1). Every view in this file is wrapped
    in @login_required, since the spec (§5.5) says everything requires
    being logged in — this decorator redirects anyone not logged in to
    Django's default login page instead of showing the page.
    """
    filtered = RequestFilter(request.GET, queryset=Request.objects.all())
    return render(request, "core/request_list.html", {"filter": filtered})

@login_required
def dashboard(request):
    context = {
        "step_counts_json": json.dumps(get_step_counts()),
        "late_by_region_json": json.dumps(get_late_by_region()),
        "average_days_by_step_json": json.dumps(get_average_days_by_step()),
        "go_lives_by_month_json": json.dumps(get_go_lives_by_month()),
        "my_open_items": get_my_open_items(request.user),
    }

    return render(request, "core/dashboard.html", context)


@login_required
@permission_required("core.add_request", raise_exception=True)
def request_create(request):
    """
    The create form (§5.3). On success, redirects to the new request's
    detail page rather than re-showing the form.

    permission_required (with raise_exception=True) means a logged-in
    user without the add_request permission — e.g. a Viewer — gets a
    403 Forbidden if they load this URL directly, not just a hidden
    button. This is the actual server-side enforcement §4 requires:
    "If someone types the URL directly, the app must still refuse them."
    """
    if request.method == "POST":
        form = RequestForm(request.POST)
        if form.is_valid():
            new_request = form.save(commit=False)
            new_request.requester = request.user
            new_request.save()
            return redirect("request_detail", pk=new_request.pk)
    else:
        form = RequestForm()

    return render(request, "core/request_form.html", {"form": form})


@login_required
def request_edit(request, pk):
    """
    Same form as create, but bound to an existing instance — plus the
    two-people-editing protection from §6c.

    HOW IT WORKS: when the page first loads (GET), the form's hidden
    'version' field is stamped with whatever version the request had AT
    THAT MOMENT. When the form is submitted (POST), we re-fetch the
    request fresh from the database and compare its CURRENT version to
    the one stamped in the hidden field. If someone else saved a change
    in between, those numbers won't match — we reject the save with a
    clear message instead of silently overwriting their edit. If they
    match, we save normally AND bump the version by 1, so the next
    editor's stale-check will correctly catch THIS save too.
    """
    req = get_object_or_404(Request, pk=pk)

    if request.method == "POST":
        form = RequestForm(request.POST, instance=req)
        submitted_version = request.POST.get("version")

        # Re-check the database's current version, not the one loaded
        # into `req` above at the start of this request — a concurrent
        # save could have happened between then and now.
        current_version = Request.objects.get(pk=pk).version

        if submitted_version and int(submitted_version) != current_version:
            messages.error(
                request,
                "This request changed while you were looking at it, please reload.",
            )
            return redirect("request_detail", pk=pk)

        if form.is_valid():
            # Capture what actually changed, so each edited field gets
            # its own history row rather than one vague "edited" entry.
            changed = [
                (field, form.initial.get(field), form.cleaned_data.get(field))
                for field in form.changed_data
                if field != "version"
            ]

            updated = form.save(commit=False)
            updated.version = current_version + 1
            updated.save()

            for field_name, old_value, new_value in changed:
                log_field_edit(
                    request=updated, actor=request.user, field_name=field_name,
                    old_value=old_value, new_value=new_value,
                )

            return redirect("request_detail", pk=req.pk)
    else:
        form = RequestForm(instance=req)

    return render(request, "core/request_form.html", {"form": form, "request_obj": req})


@login_required
def request_detail(request, pk):
    """
    The detail screen (§5.2): request info, checklist, comments,
    attachments, history, and now — the permission-aware transition
    buttons. Disabled buttons show WHY, per §5.2's exact example
    ("2 required checklist items are not done").
    """
    req = get_object_or_404(Request, pk=pk)

    comment_form = CommentForm()
    attachment_form = AttachmentForm()

    if request.method == "POST":
        if "submit_comment" in request.POST:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.request = req
                comment.author = request.user
                comment.save()
                return redirect("request_detail", pk=req.pk)

        elif "submit_attachment" in request.POST:
            attachment_form = AttachmentForm(request.POST, request.FILES)
            if attachment_form.is_valid():
                attachment = attachment_form.save(commit=False)
                attachment.request = req
                attachment.uploaded_by = request.user
                attachment.save()
                return redirect("request_detail", pk=req.pk)

    transitions = get_available_transitions(req, request.user)

    return render(
        request,
        "core/request_detail.html",
        {
            "req": req,
            "comment_form": comment_form,
            "attachment_form": attachment_form,
            "transitions": transitions,
        },
    )


@login_required
def request_transition(request, pk, target_step):
    """
    Handles the actual button click. Every path here goes through
    perform_transition() — this view NEVER sets request.current_step
    directly, per §6a's central rule.
    """
    req = get_object_or_404(Request, pk=pk)

    if request.method != "POST":
        return redirect("request_detail", pk=pk)

    reason = request.POST.get("reason", "").strip()
    expected_version = request.POST.get("expected_version")
    expected_version = int(expected_version) if expected_version else None

    try:
        if target_step == S.REJECTED:
            if len(reason) < 20:
                raise ValidationError("A rejection reason of at least 20 characters is required.")
            req.comments.create(author=request.user, text=f"Rejected: {reason}")
            perform_transition(req, S.REJECTED, actor=request.user, expected_version=expected_version)

        elif target_step == S.ON_HOLD:
            perform_transition(req, S.ON_HOLD, actor=request.user, reason=reason, expected_version=expected_version)

        else:
            # Covers both normal forward moves AND resuming from On Hold —
            # his engine.py already detects "resuming" purely from
            # req.current_step being ON_HOLD, no special keyword needed.
            perform_transition(req, target_step, actor=request.user, expected_version=expected_version)

        messages.success(request, f"Request moved to {target_step.replace('_', ' ').title()}.")

    except ValidationError as e:
        error_text = str(e.message) if hasattr(e, "message") else str(e)
        messages.error(request, error_text)

    return redirect("request_detail", pk=pk)


@login_required
def checklist_item_update(request, pk):
    """
    Lets a logged-in user tick a checklist item's status (§3: Pending,
    In Progress, Done, or Not Applicable), with an optional note.

    Per §4, only Engineer/Coordinator are supposed to tick items — that
    role check happens here, since it's a plain permission check (not a
    step transition), so it doesn't need his engine at all.
    """
    item = get_object_or_404(ChecklistItem, pk=pk)

    if request.method != "POST":
        return redirect("request_detail", pk=item.request_id)

    allowed_roles = ["Engineer", "Coordinator"]
    if not request.user.groups.filter(name__in=allowed_roles).exists():
        messages.error(request, "You don't have permission to update checklist items.")
        return redirect("request_detail", pk=item.request_id)

    new_status = request.POST.get("status")
    valid_statuses = dict(ChecklistItem.STATUS_CHOICES)
    if new_status not in valid_statuses:
        messages.error(request, "Invalid status.")
        return redirect("request_detail", pk=item.request_id)

    old_status = item.status

    item.status = new_status
    item.note = request.POST.get("note", "").strip()
    item.assignee = request.user
    item.save(update_fields=["status", "note", "assignee"])

    if old_status != new_status:
        log_checklist_change(
            request=item.request, actor=request.user, item_label=item.label,
            old_status=old_status, new_status=new_status,
        )

    messages.success(request, f"'{item.label}' marked as {valid_statuses[new_status]}.")
    return redirect("request_detail", pk=item.request_id)


@login_required
def request_csv_import(request):
    """
    Bulk-import stretch goal (§9): upload a CSV to create many drafts at
    once, showing which rows failed and why. Reuses RequestForm per row,
    so an imported row obeys the EXACT same two rules (§5.3) as a request
    created by hand through the normal form — no separate validation
    logic to maintain in two places.

    Expected CSV columns: partner_code, service, direction, priority,
    target_date, description
    """
    results = []

    if request.method == "POST":
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = request.FILES["csv_file"]
            decoded = uploaded.read().decode("utf-8-sig").splitlines()
            reader = csv.DictReader(decoded)

            for row_number, row in enumerate(reader, start=2):  # row 1 = header
                partner_code = (row.get("partner_code") or "").strip()
                partner = Partner.objects.filter(code=partner_code).first()

                if not partner:
                    results.append({
                        "row": row_number, "success": False,
                        "reason": f"No partner found with code '{partner_code}'.",
                    })
                    continue

                # version=1 satisfies RequestForm's hidden version field —
                # irrelevant here since these are brand new requests, not
                # edits, so there's nothing to conflict-check against.
                form_data = {
                    "partner": partner.id,
                    "service": (row.get("service") or "").strip(),
                    "direction": (row.get("direction") or "").strip(),
                    "priority": (row.get("priority") or "NORMAL").strip(),
                    "target_date": (row.get("target_date") or "").strip(),
                    "description": (row.get("description") or "").strip(),
                    "version": 1,
                }

                row_form = RequestForm(data=form_data)
                if row_form.is_valid():
                    new_request = row_form.save(commit=False)
                    new_request.requester = request.user
                    new_request.save()
                    results.append({"row": row_number, "success": True, "reason": ""})
                else:
                    error_text = "; ".join(
                        f"{field}: {', '.join(errs)}" for field, errs in row_form.errors.items()
                    )
                    results.append({"row": row_number, "success": False, "reason": error_text})
    else:
        form = CSVImportForm()

    return render(request, "core/csv_import.html", {"form": form, "results": results})