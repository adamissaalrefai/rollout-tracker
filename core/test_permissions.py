from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.test import TestCase


class RolePermissionsTest(TestCase):
    """
    Proves the setup_roles command assigns the correct base permissions
    to each of the five roles from the spec (§4). This tests the
    FOUNDATION layer — "can this kind of user do this kind of thing at
    all" — not the fine-grained per-transition rules, which live in
    workflow/conditions.py and get tested separately once that's built.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles")

        cls.viewer = User.objects.create_user(username="test_viewer")
        cls.viewer.groups.add(Group.objects.get(name="Viewer"))

        cls.requester = User.objects.create_user(username="test_requester")
        cls.requester.groups.add(Group.objects.get(name="Requester"))

        cls.engineer = User.objects.create_user(username="test_engineer")
        cls.engineer.groups.add(Group.objects.get(name="Engineer"))

        cls.approver = User.objects.create_user(username="test_approver")
        cls.approver.groups.add(Group.objects.get(name="Approver"))

        cls.coordinator = User.objects.create_user(username="test_coordinator")
        cls.coordinator.groups.add(Group.objects.get(name="Coordinator"))

    # --- Viewer: can look at everything, change nothing ---

    def test_viewer_can_view_requests(self):
        self.assertTrue(self.viewer.has_perm("core.view_request"))

    def test_viewer_cannot_add_request(self):
        self.assertFalse(self.viewer.has_perm("core.add_request"))

    def test_viewer_cannot_change_request(self):
        self.assertFalse(self.viewer.has_perm("core.change_request"))

    def test_viewer_cannot_change_checklist_item(self):
        self.assertFalse(self.viewer.has_perm("core.change_checklistitem"))

    # --- Requester: can create requests, cannot tick checklists ---

    def test_requester_can_add_request(self):
        self.assertTrue(self.requester.has_perm("core.add_request"))

    def test_requester_cannot_change_checklist_item(self):
        # Ticking checklist items is an Engineer/Coordinator action, not
        # a Requester one, per §4.
        self.assertFalse(self.requester.has_perm("core.change_checklistitem"))

    # --- Engineer: can tick checklist items ---

    def test_engineer_can_change_checklist_item(self):
        self.assertTrue(self.engineer.has_perm("core.change_checklistitem"))

    def test_engineer_cannot_add_request(self):
        # Only Requester/Coordinator can create requests, per §4's
        # Draft -> Submitted row.
        self.assertFalse(self.engineer.has_perm("core.add_request"))

    # --- Approver: can change requests (to approve/reject) ---

    def test_approver_can_change_request(self):
        self.assertTrue(self.approver.has_perm("core.change_request"))

    def test_approver_cannot_change_checklist_template(self):
        self.assertFalse(self.approver.has_perm("core.change_checklisttemplateitem"))

    # --- Coordinator: broadest role, can do everything above ---

    def test_coordinator_can_add_request(self):
        self.assertTrue(self.coordinator.has_perm("core.add_request"))

    def test_coordinator_can_change_checklist_item(self):
        self.assertTrue(self.coordinator.has_perm("core.change_checklistitem"))

    def test_coordinator_can_change_request(self):
        self.assertTrue(self.coordinator.has_perm("core.change_request"))

    # --- Every role should at least be able to view everything ---

    def test_every_role_can_view_requests(self):
        for user in [self.viewer, self.requester, self.engineer, self.approver, self.coordinator]:
            self.assertTrue(user.has_perm("core.view_request"))