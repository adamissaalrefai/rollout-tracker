import random
from datetime import timedelta

from django.contrib.auth.models import User, Group
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import (
    Partner,
    Request,
    ChecklistTemplateItem,
    ChecklistItem,
    SERVICE_CHOICES,
)

from workflow.engine import perform_transition
from workflow import steps as S


class Command(BaseCommand):
    """
    Creates fake demo data: one user per role, 25 partners across the
    three regions, checklist templates for all five services, and 120
    fake requests pushed through the real transition engine — so every
    request's step, and every role-check pass/fail, reflects the actual
    rules in workflow/transitions.py and conditions.py.

    STILL PENDING on the engine side (as of this file's writing):
      - No HistoryEntry rows get written on a move — so requests WILL be
        spread across steps correctly, but the history timeline stays
        empty until that's added.
      - step_entered_at and version aren't updated by perform_transition,
        so late-detection and concurrency protection won't reflect
        real transition timing yet.
      (Checklist auto-copy and the 20-char rejection check are both
      implemented now in engine.py/conditions.py, so this command no
      longer needs its own workarounds for either.)

    Run with:
        python manage.py seed_demo
    Users/partners/templates are safe to re-run (get_or_create). Requests
    are NOT reset on re-run — each run adds another ~120 on top of
    whatever already exists. Clear the Request table yourself first for
    a clean slate.
    """

    help = "Creates demo users, partners, checklist templates, and 120 requests"

    def handle(self, *args, **options):
        self.create_users_and_roles()
        self.create_partners()
        self.create_checklist_templates()
        self.create_requests()
        self.stdout.write(self.style.SUCCESS("Seed data created."))

    # ---------- users, partners, checklist templates ----------

    def create_users_and_roles(self):
        roles = ["Viewer", "Requester", "Engineer", "Approver", "Coordinator"]
        for role in roles:
            group, _ = Group.objects.get_or_create(name=role)
            username = f"demo_{role.lower()}"
            user, created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"}
            )
            if created:
                user.set_password("demo1234")
                user.save()
            user.groups.add(group)
            self.stdout.write(f"User ready: {username} / demo1234 ({role})")

        requester_group = Group.objects.get(name="Requester")
        for i in range(1, 4):
            username = f"demo_user{i}"
            user, created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"}
            )
            if created:
                user.set_password("demo1234")
                user.save()
            user.groups.add(requester_group)

    def create_partners(self):
        regions = ["EMEA", "APAC", "AMER"]
        countries_by_region = {
            "EMEA": ["Germany", "France", "UK", "Egypt", "UAE"],
            "APAC": ["Japan", "India", "Australia", "Singapore"],
            "AMER": ["USA", "Brazil", "Canada", "Mexico"],
        }
        for i in range(1, 26):
            region = regions[i % len(regions)]
            country = random.choice(countries_by_region[region])
            code = f"PT-{country[:2].upper()}-{i:03d}"
            Partner.objects.get_or_create(
                code=code,
                defaults={
                    "name": f"{country} Telecom {i}",
                    "country": country,
                    "region": region,
                    "active": True,
                },
            )
        self.stdout.write("25 partners ready.")

    def create_checklist_templates(self):
        ChecklistTemplateItem.objects.all().delete()
        default_items = {
            "TESTING": [
                ("Test plan agreed", True),
                ("Data session test passed", True),
                ("Throughput report attached", False),
            ],
            "APPROVAL": [
                ("Commercial terms approved", True),
                ("Legal sign-off", True),
            ],
            "DEPLOYMENT": [
                ("Config pushed to production", True),
                ("Smoke test done", True),
            ],
        }
        for service_code, _label in SERVICE_CHOICES:
            for step, items in default_items.items():
                for order, (label, required) in enumerate(items):
                    ChecklistTemplateItem.objects.create(
                        service=service_code, step=step, label=label,
                        required=required, order=order,
                    )
        self.stdout.write("Checklist templates ready for all 5 services.")

    # ---------- 120 requests, pushed through the real engine ----------

    def create_requests(self):
        partners = list(Partner.objects.all())
        requesters = list(User.objects.filter(groups__name="Requester"))
        coordinators = list(User.objects.filter(groups__name="Coordinator"))
        engineers = list(User.objects.filter(groups__name="Engineer"))
        approvers = list(User.objects.filter(groups__name="Approver"))
        owner_pool = list(User.objects.filter(groups__name__in=["Engineer", "Coordinator"]))

        if not all([partners, requesters, coordinators, engineers, approvers]):
            self.stdout.write(self.style.ERROR(
                "Missing partners or role users — something went wrong earlier in this command."
            ))
            return

        created_count = 0
        skipped_count = 0

        outcomes = [
            "draft", "submitted", "testing", "approval",
            "deployment", "live", "rejected", "on_hold",
        ]
        weights = [8, 12, 15, 15, 15, 20, 8, 7]

        for i in range(120):
            partner = random.choice(partners)
            service = random.choice(SERVICE_CHOICES)[0]
            direction = random.choice(["INBOUND", "OUTBOUND"])
            target_date = timezone.now().date() + timedelta(days=random.randint(5, 90))

            has_unfinished = Request.objects.filter(
                partner=partner, service=service, direction=direction
            ).exclude(current_step__in=[S.LIVE, S.REJECTED]).exists()
            if has_unfinished:
                skipped_count += 1
                continue

            req = Request.objects.create(
                partner=partner, service=service, direction=direction,
                priority=random.choice(["LOW", "NORMAL", "HIGH", "URGENT"]),
                target_date=target_date,
                requester=random.choice(requesters),
                description=f"Enable {service} for {partner.name}",
            )
            created_count += 1

            how_far = random.choices(outcomes, weights=weights)[0]

            try:
                if how_far == "draft":
                    continue

                perform_transition(req, S.SUBMITTED, actor=random.choice(requesters))
                if how_far == "submitted":
                    continue

                req.owner = random.choice(owner_pool)
                req.save(update_fields=["owner"])
                perform_transition(req, S.TESTING, actor=random.choice(coordinators))
                self._complete_checklist(req, "TESTING")
                if how_far == "testing":
                    continue

                perform_transition(req, S.APPROVAL, actor=random.choice(engineers))
                self._complete_checklist(req, "APPROVAL")
                req.comments.create(
                    author=random.choice(engineers),
                    text="Reviewed and looks good — approving to proceed.",
                )
                if how_far == "approval":
                    continue

                perform_transition(req, S.DEPLOYMENT, actor=random.choice(approvers))
                self._complete_checklist(req, "DEPLOYMENT")
                if how_far == "deployment":
                    continue

                if how_far == "live":
                    req.actual_go_live_date = timezone.now().date()
                    req.save(update_fields=["actual_go_live_date"])
                    perform_transition(req, S.LIVE, actor=random.choice(owner_pool))

                elif how_far == "rejected":
                    # A real, spec-length reason (20+ chars) even though
                    # his current check doesn't enforce that length yet.
                    req.comments.create(
                        author=random.choice(approvers),
                        text="Rejected: commercial terms could not be agreed with the partner.",
                    )
                    perform_transition(req, S.REJECTED, actor=random.choice(approvers))

                elif how_far == "on_hold":
                    perform_transition(
                        req, S.ON_HOLD,
                        actor=random.choice(coordinators),
                        reason="Waiting on legal sign-off before continuing.",
                    )

            except ValidationError as e:
                self.stdout.write(self.style.WARNING(f"Request {req.id} stopped early: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"Created {created_count} requests ({skipped_count} skipped as duplicates)."
        ))

    def _complete_checklist(self, req, step):
        """Marks all required checklist items for a step as Done. The
        items themselves are created automatically now, by
        perform_transition() copying the service's templates the moment
        the request enters this step (§3) — no manual copying needed
        here anymore."""
        req.checklist_items.filter(step=step, required=True).update(status="DONE")