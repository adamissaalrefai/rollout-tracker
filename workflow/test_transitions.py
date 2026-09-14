from datetime import timedelta

from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Partner, Request, ChecklistItem
from workflow.engine import perform_transition
from workflow import steps as S


class TransitionEngineTest(TestCase):
    """
    Tests perform_transition() against the actual rules table in §4 —
    proving allowed moves work, forbidden ones are blocked (wrong role
    OR unmet condition), and Live/Rejected are truly final. This is the
    exact requirement from §7: "Every row of the table in §4 — that
    allowed moves work and that forbidden ones are blocked."
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles")

        cls.requester = User.objects.create_user(username="requester")
        cls.requester.groups.add(Group.objects.get(name="Requester"))

        cls.engineer = User.objects.create_user(username="engineer")
        cls.engineer.groups.add(Group.objects.get(name="Engineer"))

        cls.approver = User.objects.create_user(username="approver")
        cls.approver.groups.add(Group.objects.get(name="Approver"))

        cls.coordinator = User.objects.create_user(username="coordinator")
        cls.coordinator.groups.add(Group.objects.get(name="Coordinator"))

        cls.viewer = User.objects.create_user(username="viewer")
        cls.viewer.groups.add(Group.objects.get(name="Viewer"))

        cls.partner = Partner.objects.create(
            code="PT-TE-001", name="Test Telecom", country="Testland",
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

    # --- Draft -> Submitted ---

    def test_requester_can_submit(self):
        req = self._new_request()
        perform_transition(req, S.SUBMITTED, actor=self.requester)
        self.assertEqual(req.current_step, S.SUBMITTED)

    def test_engineer_cannot_submit(self):
        # Only Requester/Coordinator are allowed here, per §4.
        req = self._new_request()
        with self.assertRaises(ValidationError):
            perform_transition(req, S.SUBMITTED, actor=self.engineer)

    # --- Submitted -> Testing ---

    def test_coordinator_can_move_to_testing_once_owner_assigned(self):
        req = self._new_request(current_step=S.SUBMITTED, owner=self.engineer)
        perform_transition(req, S.TESTING, actor=self.coordinator)
        self.assertEqual(req.current_step, S.TESTING)

    def test_cannot_move_to_testing_without_owner(self):
        req = self._new_request(current_step=S.SUBMITTED)  # no owner set
        with self.assertRaises(ValidationError):
            perform_transition(req, S.TESTING, actor=self.coordinator)

    def test_engineer_cannot_move_submitted_to_testing(self):
        # Only Coordinator can do this move, per §4 — Engineer acts later.
        req = self._new_request(current_step=S.SUBMITTED, owner=self.engineer)
        with self.assertRaises(ValidationError):
            perform_transition(req, S.TESTING, actor=self.engineer)

    # --- Testing -> Approval ---

    def test_cannot_leave_testing_with_incomplete_checklist(self):
        req = self._new_request(current_step=S.TESTING)
        ChecklistItem.objects.create(
            request=req, step="TESTING", label="Test plan agreed",
            required=True, status="PENDING",
        )
        with self.assertRaises(ValidationError):
            perform_transition(req, S.APPROVAL, actor=self.engineer)

    def test_engineer_can_move_to_approval_once_checklist_done(self):
        req = self._new_request(current_step=S.TESTING)
        ChecklistItem.objects.create(
            request=req, step="TESTING", label="Test plan agreed",
            required=True, status="DONE",
        )
        perform_transition(req, S.APPROVAL, actor=self.engineer)
        self.assertEqual(req.current_step, S.APPROVAL)

    # --- Approval -> Deployment ---

    def test_only_approver_can_approve(self):
        req = self._new_request(current_step=S.APPROVAL)
        req.comments.create(author=self.coordinator, text="Approved, proceed.")
        with self.assertRaises(ValidationError):
            perform_transition(req, S.DEPLOYMENT, actor=self.coordinator)

    def test_approval_requires_a_comment(self):
        req = self._new_request(current_step=S.APPROVAL)
        # no checklist items needed since none are required=True here,
        # but a comment IS required per §4's "Needs" column.
        with self.assertRaises(ValidationError):
            perform_transition(req, S.DEPLOYMENT, actor=self.approver)

    def test_approver_can_move_to_deployment_with_comment(self):
        req = self._new_request(current_step=S.APPROVAL)
        req.comments.create(author=self.approver, text="Approved, proceed.")
        perform_transition(req, S.DEPLOYMENT, actor=self.approver)
        self.assertEqual(req.current_step, S.DEPLOYMENT)

    # --- Deployment -> Live ---

    def test_live_requires_actual_go_live_date(self):
        req = self._new_request(current_step=S.DEPLOYMENT)
        with self.assertRaises(ValidationError):
            perform_transition(req, S.LIVE, actor=self.engineer)

    def test_engineer_can_move_to_live_with_go_live_date(self):
        req = self._new_request(current_step=S.DEPLOYMENT, actual_go_live_date=timezone.now().date())
        perform_transition(req, S.LIVE, actor=self.engineer)
        self.assertEqual(req.current_step, S.LIVE)

    # --- Rejected: from multiple steps, Approver/Coordinator only ---

    def test_approver_can_reject_from_testing(self):
        req = self._new_request(current_step=S.TESTING)
        req.comments.create(author=self.approver, text="Rejected: terms not agreed.")
        perform_transition(req, S.REJECTED, actor=self.approver)
        self.assertEqual(req.current_step, S.REJECTED)

    def test_engineer_cannot_reject(self):
        req = self._new_request(current_step=S.TESTING)
        req.comments.create(author=self.engineer, text="Rejected: terms not agreed.")
        with self.assertRaises(ValidationError):
            perform_transition(req, S.REJECTED, actor=self.engineer)

    # --- On Hold + resume ---

    def test_coordinator_can_put_on_hold_with_reason(self):
        req = self._new_request(current_step=S.TESTING)
        perform_transition(req, S.ON_HOLD, actor=self.coordinator, reason="Waiting on legal.")
        self.assertEqual(req.current_step, S.ON_HOLD)
        self.assertEqual(req.on_hold_from_step, S.TESTING)

    def test_on_hold_requires_a_reason(self):
        req = self._new_request(current_step=S.TESTING)
        with self.assertRaises(ValidationError):
            perform_transition(req, S.ON_HOLD, actor=self.coordinator, reason="")

    def test_engineer_cannot_put_on_hold(self):
        req = self._new_request(current_step=S.TESTING)
        with self.assertRaises(ValidationError):
            perform_transition(req, S.ON_HOLD, actor=self.engineer, reason="Waiting on legal.")

    def test_coordinator_can_resume_from_hold(self):
        req = self._new_request(current_step=S.TESTING)
        perform_transition(req, S.ON_HOLD, actor=self.coordinator, reason="Waiting on legal.")
        perform_transition(req, S.TESTING, actor=self.coordinator)
        self.assertEqual(req.current_step, S.TESTING)
        self.assertIsNone(req.on_hold_from_step)

    # --- Live and Rejected are truly final ---

    def test_cannot_move_a_live_request_anywhere(self):
        req = self._new_request(current_step=S.LIVE)
        with self.assertRaises(ValidationError):
            perform_transition(req, S.TESTING, actor=self.coordinator)

    def test_cannot_move_a_rejected_request_anywhere(self):
        req = self._new_request(current_step=S.REJECTED)
        with self.assertRaises(ValidationError):
            perform_transition(req, S.TESTING, actor=self.coordinator)

    # --- Skipping steps is never allowed ---

    def test_cannot_skip_from_draft_straight_to_testing(self):
        req = self._new_request()  # still in Draft
        with self.assertRaises(ValidationError):
            perform_transition(req, S.TESTING, actor=self.coordinator)