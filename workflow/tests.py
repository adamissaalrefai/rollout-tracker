from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.core.exceptions import ValidationError
from core.models import Partner, Request, ChecklistItem, Comment
from workflow.engine import perform_transition
from django.contrib.auth.models import User , Group, AnonymousUser


class TransitionTests(TestCase):
    def setUp(self):
     self.requester = User.objects.create_user(
        username="requester",
        password="testpass123",
     )

     self.engineer = User.objects.create_user(
        username="engineer",
        password="testpass123",
     )

     self.approver = User.objects.create_user(
        username="approver",
        password="testpass123",
     )

     self.coordinator = User.objects.create_user(
        username="coordinator",
        password="testpass123",
     )

     self.viewer = User.objects.create_user(
        username="viewer",
        password="testpass123",
     )

     requester_group = Group.objects.create(name="Requester")
     engineer_group = Group.objects.create(name="Engineer")
     approver_group = Group.objects.create(name="Approver")
     coordinator_group = Group.objects.create(name="Coordinator")
     viewer_group = Group.objects.create(name="Viewer")

     requester_group.user_set.add(self.requester)
     engineer_group.user_set.add(self.engineer)
     approver_group.user_set.add(self.approver)
     coordinator_group.user_set.add(self.coordinator)
     viewer_group.user_set.add(self.viewer)

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
        requester=self.requester,
     )

    # Keep this temporarily so the existing tests don't all need
    # to be rewritten at once.
     self.user = self.requester

    def test_allowed_transition(self):
        perform_transition(self.request, "SUBMITTED",self.requester)

        self.request.refresh_from_db()

        self.assertEqual(self.request.current_step, "SUBMITTED")

    def test_invalid_transition(self):
        with self.assertRaises(ValidationError):
            perform_transition(self.request, "LIVE",self.requester)
    
    def test_testing_requires_owner(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "TESTING",self.coordinator)
    
    
    def test_testing_requires_checklist(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING",self.coordinator)

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Run testing checklist",
        required=True,
        status="PENDING",
     )

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "APPROVAL",self.engineer)
    
    def test_testing_allows_approval_when_checklist_complete(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING",self.coordinator)

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Run testing checklist",
        required=True,
        status="DONE",
     )

     perform_transition(self.request, "APPROVAL",self.engineer)

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "APPROVAL")
    
    def test_approval_requires_checklist(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING",self.coordinator)

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing checklist",
        required=True,
        status="DONE",
     )

     perform_transition(self.request, "APPROVAL",self.engineer)

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
        perform_transition(self.request, "DEPLOYMENT",self.approver)
    
    def test_approval_requires_comment(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING",self.coordinator)

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing checklist",
        required=True,
        status="DONE",
     )

     perform_transition(self.request, "APPROVAL",self.engineer)

     ChecklistItem.objects.create(
        request=self.request,
        step="APPROVAL",
        label="Approval checklist",
        required=True,
        status="DONE",
     )

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "DEPLOYMENT",self.approver)
        
    def test_approval_allows_deployment(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING",self.coordinator)

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing checklist",
        required=True,
        status="DONE",
     )

     perform_transition(self.request, "APPROVAL",self.engineer)

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

     perform_transition(self.request, "DEPLOYMENT",self.approver)

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "DEPLOYMENT")
     
     
    def test_deployment_requires_go_live_date(self):
      perform_transition(self.request, "SUBMITTED",self.requester)

      self.request.owner = self.user
      self.request.save()

      perform_transition(self.request, "TESTING",self.coordinator)

    # Make Testing checklist complete
      ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing item",
        required=True,
        status="DONE",
     )

      perform_transition(self.request, "APPROVAL",self.engineer)

    # Make Approval checklist complete + add required comment
      ChecklistItem.objects.create(
        request=self.request,
        step="APPROVAL",
        label="Approval item",
        required=True,
        status="DONE",
     )

      Comment.objects.create(
        request=self.request,
        author=self.user,
        text="Approved.",
     )

      perform_transition(self.request, "DEPLOYMENT",self.approver)

    # Deployment checklist is complete, but no actual_go_live_date
      ChecklistItem.objects.create(
        request=self.request,
        step="DEPLOYMENT",
        label="Deployment item",
        required=True,
        status="DONE",
     )

      with self.assertRaises(ValidationError):
        perform_transition(self.request, "LIVE",self.engineer)
   
    def test_can_put_request_on_hold(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     perform_transition(self.request, "ON_HOLD",self.coordinator,reason="Waiting for partner confirmation.",)

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "ON_HOLD")
     self.assertEqual(self.request.on_hold_from_step, "SUBMITTED")


    def test_can_resume_from_on_hold(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     perform_transition(self.request, "ON_HOLD",self.coordinator,reason="Waiting for partner confirmation.")
     perform_transition(self.request, "SUBMITTED",self.coordinator)

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "SUBMITTED")
     self.assertIsNone(self.request.on_hold_from_step)


    def test_cannot_resume_to_wrong_step(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING",self.coordinator)
     perform_transition(self.request, "ON_HOLD",self.coordinator,reason="Waiting for partner confirmation.",)

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "APPROVAL",self.coordinator)

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "ON_HOLD")
     self.assertEqual(self.request.on_hold_from_step, "TESTING")
   
    def test_rejection_requires_reason(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "REJECTED",self.approver)

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "SUBMITTED")


    def test_can_reject_with_reason(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     Comment.objects.create(
        request=self.request,
        author=self.user,
        text="Partner failed the required requirements.",
     )

     perform_transition(self.request, "REJECTED",self.approver)

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "REJECTED")
     
    def test_live_is_terminal(self):
     perform_transition(self.request, "SUBMITTED",self.requester)

     self.request.owner = self.user
     self.request.save()

     perform_transition(self.request, "TESTING",self.coordinator)

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing item",
        required=True,
        status="DONE",
     )

     perform_transition(self.request, "APPROVAL",self.engineer)

     ChecklistItem.objects.create(
        request=self.request,
        step="APPROVAL",
        label="Approval item",
        required=True,
        status="DONE",
     )

     Comment.objects.create(
        request=self.request,
        author=self.user,
        text="Approved.",
     )

     perform_transition(self.request, "DEPLOYMENT",self.approver)

     ChecklistItem.objects.create(
        request=self.request,
        step="DEPLOYMENT",
        label="Deployment item",
        required=True,
        status="DONE",
     )

     self.request.actual_go_live_date = date.today()
     self.request.save()
 
     perform_transition(self.request, "LIVE",self.engineer)

     with self.assertRaises(ValidationError):
        perform_transition(self.request, "DEPLOYMENT",self.engineer)

     self.request.refresh_from_db()
     self.assertEqual(self.request.current_step, "LIVE")


    def test_rejected_is_terminal(self):
     perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
     )

     Comment.objects.create(
        request=self.request,
        author=self.user,
        text="Requirements were not met.",
     )

     perform_transition(
        self.request,
        "REJECTED",
        self.approver,
     )

     with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "TESTING",
            self.engineer,
         )

     self.request.refresh_from_db()

     self.assertEqual(self.request.current_step, "REJECTED")


    def test_engineer_cannot_submit(self):
      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "SUBMITTED",
            self.engineer,
         )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "DRAFT")


    def test_engineer_cannot_approve_deployment(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
     )

      self.request.owner = self.user
      self.request.save()

      perform_transition(
        self.request,
        "TESTING",
        self.coordinator,
     )

      ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing item",
        required=True,
        status="DONE",
     )

      perform_transition(
        self.request,
        "APPROVAL",
        self.engineer,
     )

      ChecklistItem.objects.create(
        request=self.request,
        step="APPROVAL",
        label="Approval item",
        required=True,
        status="DONE",
     )

      Comment.objects.create(
        request=self.request,
        author=self.user,
        text="Approval review completed.",
     )

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "DEPLOYMENT",
            self.engineer,
         )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "APPROVAL")


    def test_approver_cannot_move_testing_to_approval(self):
     perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
     )

     self.request.owner = self.user
     self.request.save()

     perform_transition(
        self.request,
        "TESTING",
        self.coordinator,
     )

     ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing item",
        required=True,
        status="DONE",
     )

     with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "APPROVAL",
            self.approver,
         )

     self.request.refresh_from_db()
     self.assertEqual(self.request.current_step, "TESTING")


    def test_requester_cannot_put_request_on_hold(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
     )

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "ON_HOLD",
            self.requester,
         )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "SUBMITTED")


    def test_approver_cannot_put_request_on_hold(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
     )

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "ON_HOLD",
            self.approver,
         )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "SUBMITTED")
      
    def test_coordinator_can_reject(self):
       perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
     )

       Comment.objects.create(
        request=self.request,
        author=self.user,
        text="The request does not meet the required requirements.",
       )

       perform_transition(
        self.request,
        "REJECTED",
        self.coordinator,
       )

       self.request.refresh_from_db()

       self.assertEqual(self.request.current_step, "REJECTED")
       
    def test_viewer_cannot_transition(self):
      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "SUBMITTED",
            self.viewer,
         )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "DRAFT")
      
    def test_requester_cannot_reject(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
      )

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "REJECTED",
            self.requester,
          )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "SUBMITTED")
      
    def test_engineer_cannot_reject(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
     )

      self.request.owner = self.user
      self.request.save()

      perform_transition(
        self.request,
        "TESTING",
        self.coordinator,
     )

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "REJECTED",
            self.engineer,
         )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "TESTING")
      
    def test_approver_cannot_go_live(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
      )

      self.request.owner = self.user
      self.request.save()

      perform_transition(
        self.request,
        "TESTING",
        self.coordinator,
     )

      ChecklistItem.objects.create(
        request=self.request,
        step="TESTING",
        label="Testing item",
        required=True,
        status="DONE",
     )

      perform_transition(
        self.request,
        "APPROVAL",
        self.engineer,
     )

      ChecklistItem.objects.create(
        request=self.request,
        step="APPROVAL",
        label="Approval item",
        required=True,
        status="DONE",
     )

      Comment.objects.create(
        request=self.request,
        author=self.user,
        text="Approval review completed.",
     )

      perform_transition(
        self.request,
        "DEPLOYMENT",
        self.approver,
     )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "DEPLOYMENT")

      ChecklistItem.objects.create(
        request=self.request,
        step="DEPLOYMENT",
        label="Deployment item",
        required=True,
        status="DONE",
     )

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "LIVE",
            self.approver,
         )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "DEPLOYMENT")
      
      
    def test_engineer_cannot_resume_from_on_hold(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
      )

      perform_transition(
        self.request,
        "ON_HOLD",
        self.coordinator,reason="Waiting for partner confirmation.",
     )

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "SUBMITTED",
            self.engineer,
         )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "ON_HOLD")
      
    def test_coordinator_can_resume(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
     )

      perform_transition(
        self.request,
        "ON_HOLD",
        self.coordinator,reason="Waiting for partner confirmation.",
      )

      perform_transition(
        self.request,
        "SUBMITTED",
        self.coordinator,
      )

      self.request.refresh_from_db()

      self.assertEqual(self.request.current_step, "SUBMITTED")
      self.assertIsNone(self.request.on_hold_from_step)
      
    def test_unauthenticated_user_cannot_transition(self):
      actor = AnonymousUser()

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "SUBMITTED",
            actor,
          )

      self.request.refresh_from_db()
      self.assertEqual(self.request.current_step, "DRAFT")
      
    def test_on_hold_requires_reason(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
     )

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "ON_HOLD",
            self.coordinator,
          )

      self.request.refresh_from_db()

      self.assertEqual(self.request.current_step, "SUBMITTED")
      self.assertIsNone(self.request.on_hold_from_step)
      
    def test_coordinator_can_put_request_on_hold_with_reason(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
      )

      reason = "Waiting for partner confirmation."

      perform_transition(
        self.request,
        "ON_HOLD",
        self.coordinator,
        reason=reason,
      )

      self.request.refresh_from_db()

      self.assertEqual(self.request.current_step, "ON_HOLD")
      self.assertEqual(self.request.on_hold_from_step, "SUBMITTED")
      self.assertEqual(self.request.on_hold_reason, reason)
      
    def test_resuming_clears_on_hold_reason(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
      )

      perform_transition(
        self.request,
        "ON_HOLD",
        self.coordinator,
        reason="Waiting for partner confirmation.",
     )

      perform_transition(
        self.request,
        "SUBMITTED",
        self.coordinator,
     )

      self.request.refresh_from_db()

      self.assertEqual(self.request.current_step, "SUBMITTED")
      self.assertIsNone(self.request.on_hold_from_step)
      self.assertEqual(self.request.on_hold_reason, "")
      
    def test_engineer_cannot_put_request_on_hold(self):
      perform_transition(
        self.request,
        "SUBMITTED",
        self.requester,
      )

      with self.assertRaises(ValidationError):
        perform_transition(
            self.request,
            "ON_HOLD",
            self.engineer,
            reason="Testing reason.",
         )

      self.request.refresh_from_db()

      self.assertEqual(self.request.current_step, "SUBMITTED")