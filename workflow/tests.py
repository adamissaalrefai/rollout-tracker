from django.contrib.auth.models import User
from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import Partner, Request, ChecklistItem, Comment
from workflow.engine import perform_transition


class TransitionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )

        self.partner = Partner.objects.create(
            code="PT-TEST-001",
            name="Test Partner",
            country="Egypt",
            region="EMEA",
        )

        self.request = Request.objects.create(
            partner=self.partner,
            service="VOICE",
            direction="INBOUND",
            priority="NORMAL",
            target_date="2026-12-01",
            requester=self.user,
        )

    def test_allowed_transition(self):
        perform_transition(self.request, "SUBMITTED")

        self.request.refresh_from_db()

        self.assertEqual(self.request.current_step, "SUBMITTED")

    def test_invalid_transition(self):
        with self.assertRaises(ValidationError):
            perform_transition(self.request, "LIVE")
    
    def test_testing_requires_owner(self):
     perform_transition(self.request, "SUBMITTED")

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "TESTING")
    
    
    def test_testing_requires_checklist(self):
     perform_transition(self.request, "SUBMITTED")

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING")

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Run testing checklist",
        required=True,
        status="PENDING",
     )

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "APPROVAL")
    
    def test_testing_allows_approval_when_checklist_complete(self):
     perform_transition(self.request, "SUBMITTED")

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING")

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Run testing checklist",
        required=True,
        status="DONE",
     )

     perform_transition(self.request, "APPROVAL")

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "APPROVAL")
    
    def test_approval_requires_checklist(self):
     perform_transition(self.request, "SUBMITTED")

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING")

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing checklist",
        required=True,
        status="DONE",
     )

     perform_transition(self.request, "APPROVAL")

     ChecklistItem.objects.create(
        request=self.request,
        step="APPROVAL",
        label="Approval checklist",
        required=True,
        status="PENDING",
     )

     Comment.objects.create(
        request=self.request,
        author=self.user,
        text="Approval review completed.",
     )

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "DEPLOYMENT")
    
    def test_approval_requires_comment(self):
     perform_transition(self.request, "SUBMITTED")

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING")

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing checklist",
        required=True,
        status="DONE",
     )

     perform_transition(self.request, "APPROVAL")

     ChecklistItem.objects.create(
        request=self.request,
        step="APPROVAL",
        label="Approval checklist",
        required=True,
        status="DONE",
     )

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "DEPLOYMENT")
        
    def test_approval_allows_deployment(self):
     perform_transition(self.request, "SUBMITTED")

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING")

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing checklist",
        required=True,
        status="DONE",
     )

     perform_transition(self.request, "APPROVAL")

     ChecklistItem.objects.create(
        request=self.request,
        step="APPROVAL",
        label="Approval checklist",
        required=True,
        status="DONE",
     )

     Comment.objects.create(
        request=self.request,
        author=self.user,
        text="Approval review completed.",
     )

     perform_transition(self.request, "DEPLOYMENT")

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "DEPLOYMENT")
