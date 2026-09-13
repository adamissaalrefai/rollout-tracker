from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Creates the five roles from the spec (§4) as Django Groups and gives
    each one a starting set of model-level permissions.

    IMPORTANT — what this command does NOT do:
    Django's built-in permissions only say things like "can this user change
    a Request at all." They can't express the finer rules from §4, like
    "an Engineer can only move Testing -> Approval" or "only if all required
    checklist items are Done." Those specific rules belong in your
    teammate's workflow/conditions.py and engine.py, which will check
    "is this user in the Coordinator group?" on top of these base
    permissions. Think of Groups as the first, coarse gate — the engine is
    the second, precise gate.

    Run with:
        python manage.py setup_roles
    Safe to run more than once — get_or_create won't duplicate anything.
    """

    help = "Creates the five roles (Viewer, Requester, Engineer, Approver, Coordinator) as Groups"

    def handle(self, *args, **options):
        # Model names as Django auto-generates permission codenames for them:
        # add_<model>, change_<model>, delete_<model>, view_<model>
        core_models = [
            "partner",
            "request",
            "checklistitem",
            "checklisttemplateitem",
            "comment",
            "attachment",
        ]

        def perms(*codenames_with_models):
            """Looks up Permission objects by 'action_modelname' strings."""
            result = []
            for entry in codenames_with_models:
                action, model = entry.split("_", 1)
                try:
                    result.append(
                        Permission.objects.get(
                            codename=f"{action}_{model}",
                            content_type__model=model,
                        )
                    )
                except Permission.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"Permission {entry} not found — skipping")
                    )
            return result

        view_all = [f"view_{m}" for m in core_models]

        role_permissions = {
            # Viewer: read-only, everywhere.
            "Viewer": view_all,

            # Requester: can see everything, create requests, add comments
            # and attachments to support their own requests. Restricting
            # them to only THEIR OWN drafts is an object-level rule (which
            # request?), not a Django Group permission — that check happens
            # in the engine/views, not here.
            "Requester": view_all + ["add_request", "change_request", "add_comment", "add_attachment"],

            # Engineer: ticks checklist items, moves requests at their steps.
            "Engineer": view_all + ["change_checklistitem", "change_request", "add_comment"],

            # Approver: approves/rejects at the Approval step.
            "Approver": view_all + ["change_request", "add_comment"],

            # Coordinator: broadest role — assigns owners, holds/resumes,
            # plus everything the other roles can do.
            "Coordinator": view_all + [
                "add_request", "change_request",
                "change_checklistitem",
                "add_comment", "add_attachment",
                "change_checklisttemplateitem", "add_checklisttemplateitem",
            ],
        }

        for role_name, codenames in role_permissions.items():
            group, created = Group.objects.get_or_create(name=role_name)
            group.permissions.set(perms(*codenames))
            status = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{status} group: {role_name}"))