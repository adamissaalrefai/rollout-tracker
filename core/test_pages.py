from datetime import timedelta

from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Partner, Request


class PageTests(TestCase):
    """
    §7's "at least three page tests" — hits real URLs with Django's test
    client, the same way a browser would, rather than testing functions
    directly. Specifically proves §4's rule that hiding a button isn't
    security: a Viewer is blocked from the CREATE URL even if they type
    it directly, not just that the button doesn't render for them.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles")

        cls.viewer = User.objects.create_user(username="page_viewer", password="pass1234")
        cls.viewer.groups.add(Group.objects.get(name="Viewer"))

        cls.requester = User.objects.create_user(username="page_requester", password="pass1234")
        cls.requester.groups.add(Group.objects.get(name="Requester"))

        cls.partner = Partner.objects.create(
            code="PT-TE-003", name="Test Telecom 3", country="Testland",
            region="EMEA", active=True,
        )
        cls.request_obj = Request.objects.create(
            partner=cls.partner, service="DATA_5G", direction="OUTBOUND",
            target_date=timezone.now().date() + timedelta(days=10),
            requester=cls.requester,
        )

    def test_list_page_requires_login(self):
        # §5.5: "Everything requires being logged in."
        response = self.client.get(reverse("request_list"))
        self.assertEqual(response.status_code, 302)  # redirected to login
        self.assertIn("/login/", response.url)

    def test_logged_in_user_can_view_list_page(self):
        self.client.login(username="page_viewer", password="pass1234")
        response = self.client.get(reverse("request_list"))
        self.assertEqual(response.status_code, 200)

    def test_detail_page_shows_the_right_request(self):
        self.client.login(username="page_requester", password="pass1234")
        response = self.client.get(reverse("request_detail", args=[self.request_obj.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.partner.name)

    def test_requester_can_create_a_request_through_the_form(self):
        self.client.login(username="page_requester", password="pass1234")
        response = self.client.post(reverse("request_create"), {
            "partner": self.partner.id,
            "service": "VOICE",
            "direction": "INBOUND",
            "priority": "NORMAL",
            "target_date": (timezone.now().date() + timedelta(days=15)).isoformat(),
            "description": "New request via page test",
            "version": 1,
        })
        self.assertEqual(response.status_code, 302)  # redirected to detail on success
        self.assertTrue(
            Request.objects.filter(service="VOICE", direction="INBOUND").exists()
        )

    def test_viewer_cannot_reach_create_page_by_typing_the_url(self):
        """
        THE important test per §4: "Hiding a button is not security...
        Write tests that prove it." A Viewer has no add_request
        permission — request_create() is decorated with
        @permission_required("core.add_request", raise_exception=True),
        so this must be blocked with a 403 even though the Viewer is
        fully logged in and typing the URL directly, not clicking a
        hidden button.
        """
        self.client.login(username="page_viewer", password="pass1234")
        response = self.client.get(reverse("request_create"))
        self.assertEqual(response.status_code, 403)

    def test_requester_CAN_reach_create_page(self):
        # Sanity check alongside the test above — proves the permission
        # check blocks the WRONG role without accidentally blocking
        # everyone.
        self.client.login(username="page_requester", password="pass1234")
        response = self.client.get(reverse("request_create"))
        self.assertEqual(response.status_code, 200)