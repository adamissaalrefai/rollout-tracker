from datetime import timedelta

from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Partner, Request
from workflow.models import HistoryEntry
from workflow.engine import perform_transition
from workflow.history import log_history
from workflow import steps as S


class AppendOnlyHistoryTest(TestCase):
    """
    §6b requires the history log to be append-only, and explicitly says
    to "write the test that proves your block works" — that's what this
    class is. Covers single-row edits, single deletes, and the bulk
    versions of both.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles")
        cls.coordinator = User.objects.create_user(username="coordinator")
        cls.coordinator.groups.add(Group.objects.get(name="Coordinator"))
        cls.partner = Partner.objects.create(
            code="PT-TE-001", name="Test Telecom", country="Testland",
            region="EMEA", active=True,
        )

    def _new_entry(self):
        req = Request.objects.create(
            partner=self.partner, service="DATA_5G", direction="OUTBOUND",
            target_date=timezone.now().date() + timedelta(days=10),
            requester=self.coordinator,
        )
        return log_history(
            request=req, actor=self.coordinator, action="STEP_CHANGE",
            field_changed="current_step", old_value="DRAFT", new_value="SUBMITTED",
        )

    def test_history_row_cannot_be_edited(self):
        entry = self._new_entry()
        entry.new_value = "TAMPERED"
        with self.assertRaises(ValidationError):
            entry.save()

    def test_history_row_cannot_be_deleted(self):
        entry = self._new_entry()
        with self.assertRaises(ValidationError):
            entry.delete()

    def test_history_cannot_be_bulk_updated(self):
        self._new_entry()
        with self.assertRaises(ValidationError):
            HistoryEntry.objects.all().update(new_value="TAMPERED")

    def test_history_cannot_be_bulk_deleted(self):
        self._new_entry()
        with self.assertRaises(ValidationError):
            HistoryEntry.objects.all().delete()

    def test_history_rows_can_still_be_created(self):
        # The block must stop edits/deletes WITHOUT stopping new appends.
        before = HistoryEntry.objects.count()
        self._new_entry()
        self.assertEqual(HistoryEntry.objects.count(), before + 1)


class TransitionWritesHistoryTest(TestCase):
    """Proves perform_transition() actually records what it did."""

    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles")
        cls.requester = User.objects.create_user(username="requester")
        cls.requester.groups.add(Group.objects.get(name="Requester"))
        cls.coordinator = User.objects.create_user(username="coordinator")
        cls.coordinator.groups.add(Group.objects.get(name="Coordinator"))
        cls.partner = Partner.objects.create(
            code="PT-TE-002", name="Test Telecom 2", country="Testland",
            region="EMEA", active=True,
        )

    def _new_request(self, **overrides):
        data = dict(
            partner=self.partner, service="DATA_5G", direction="OUTBOUND",
            target_date=timezone.now().date() + timedelta(days=10),
            requester=self.requester,
        )
        data.update(overrides)
        return Request.objects.create(**data)

    def test_transition_creates_a_history_row(self):
        req = self._new_request()
        self.assertEqual(req.history.count(), 0)

        perform_transition(req, S.SUBMITTED, actor=self.requester)

        self.assertEqual(req.history.count(), 1)
        entry = req.history.first()
        self.assertEqual(entry.action, "STEP_CHANGE")
        self.assertEqual(entry.old_value, S.DRAFT)
        self.assertEqual(entry.new_value, S.SUBMITTED)
        self.assertEqual(entry.actor, self.requester)

    def test_failed_transition_writes_no_history(self):
        # A move that gets rejected must leave no trace — the log should
        # never claim something happened that didn't.
        req = self._new_request(current_step=S.SUBMITTED)  # no owner assigned
        with self.assertRaises(ValidationError):
            perform_transition(req, S.TESTING, actor=self.coordinator)
        self.assertEqual(req.history.count(), 0)

    def test_transition_updates_step_entered_at_and_version(self):
        req = self._new_request()
        original_entered = req.step_entered_at
        original_version = req.version

        perform_transition(req, S.SUBMITTED, actor=self.requester)

        self.assertGreater(req.step_entered_at, original_entered)
        self.assertEqual(req.version, original_version + 1)

    def test_on_hold_and_resume_both_log_history(self):
        req = self._new_request(current_step=S.TESTING)
        perform_transition(req, S.ON_HOLD, actor=self.coordinator, reason="Waiting on legal.")
        perform_transition(req, S.TESTING, actor=self.coordinator)

        self.assertEqual(req.history.count(), 2)
        actions = [e.new_value for e in req.history.all()]
        self.assertEqual(actions, [S.ON_HOLD, S.TESTING])