from django.core.mail import send_mail
from django.conf import settings
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import Request

# Holds each request's step at the moment BEFORE a save happens, keyed by
# pk, so post_save can compare "what it was" to "what it is now" and tell
# whether this particular save actually changed the step. Cleared as soon
# as it's read, so it never grows unbounded.
_step_before_save = {}


@receiver(pre_save, sender=Request)
def remember_step_before_save(sender, instance, **kwargs):
    if not instance.pk:
        # Brand new request being created — there's no "before" to compare.
        _step_before_save[instance.pk] = None
        return
    try:
        _step_before_save[instance.pk] = Request.objects.get(pk=instance.pk).current_step
    except Request.DoesNotExist:
        _step_before_save[instance.pk] = None


@receiver(post_save, sender=Request)
def email_on_step_change(sender, instance, created, **kwargs):
    """
    Sends an email to the owner and requester whenever a Request's
    current_step actually changes on save (§7: "When a request moves,
    email the owner and the requester"). Uses Django's console email
    backend, per the spec — emails print to your terminal, nothing
    actually gets sent anywhere.

    Fires on ANY save that changes current_step, regardless of what
    triggered it — perform_transition(), the admin, a script — since it
    hooks the model itself rather than one specific code path.
    """
    previous_step = _step_before_save.pop(instance.pk, None)

    if created or previous_step is None or previous_step == instance.current_step:
        return  # brand new request (still Draft), or no real step change

    recipients = []
    if instance.owner and instance.owner.email:
        recipients.append(instance.owner.email)
    if instance.requester.email:
        recipients.append(instance.requester.email)
    recipients = list(set(recipients))  # dedupe in case owner == requester

    if not recipients:
        return

    send_mail(
        subject=f"Request #{instance.id} moved to {instance.get_current_step_display()}",
        message=(
            f"Request #{instance.id} ({instance.partner.name} / "
            f"{instance.get_service_display()}) moved from "
            f"{previous_step} to {instance.current_step}."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@rollout-tracker.local"),
        recipient_list=recipients,
        fail_silently=True,
    )