from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404

from .models import Request
from .forms import RequestForm, CommentForm, AttachmentForm
from .filters import RequestFilter
from .csv_export import export_requests_csv  # re-exported here so urls.py has one place to import views from

from workflow.engine import perform_transition, CONDITIONS
from workflow.transitions import TRANSITIONS
from workflow import steps as S

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
def request_create(request):
    """The create form (§5.3). On success, redirects to the new
    request's detail page rather than re-showing the form."""
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
    """Same form as create, but bound to an existing instance."""
    req = get_object_or_404(Request, pk=pk)

    if request.method == "POST":
        form = RequestForm(request.POST, instance=req)
        if form.is_valid():
            form.save()
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

    try:
        if target_step == S.REJECTED:
            if len(reason) < 20:
                raise ValidationError("A rejection reason of at least 20 characters is required.")
            req.comments.create(author=request.user, text=f"Rejected: {reason}")
            perform_transition(req, S.REJECTED, actor=request.user)

        elif target_step == S.ON_HOLD:
            perform_transition(req, S.ON_HOLD, actor=request.user, reason=reason)

        else:
            # Covers both normal forward moves AND resuming from On Hold —
            # his engine.py already detects "resuming" purely from
            # req.current_step being ON_HOLD, no special keyword needed.
            perform_transition(req, target_step, actor=request.user)

        messages.success(request, f"Request moved to {target_step.replace('_', ' ').title()}.")

    except ValidationError as e:
        error_text = str(e.message) if hasattr(e, "message") else str(e)
        messages.error(request, error_text)

    return redirect("request_detail", pk=pk)