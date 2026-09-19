from django.contrib.auth.models import Group, User
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Partner, Request


class RequestAPITestCase(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="api_user",
            password="testpass123",
        )

        self.partner = Partner.objects.create(
            name="Test Partner",
            code="TEST001",
            region="EMEA",
        )

        self.request = Request.objects.create(
            partner=self.partner,
            service="VOICE",
            direction="INBOUND",
            priority="HIGH",
            target_date="2026-12-01",
            requester=self.user,
            current_step="DRAFT",
            description="Test rollout request",
        )

        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}"
        )

    def test_list_requests_requires_authentication(self):
        self.client.credentials()

        response = self.client.get("/api/requests/")

        self.assertEqual(response.status_code, 401)

    def test_authenticated_user_can_list_requests(self):
        response = self.client.get("/api/requests/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.request.id)

    def test_authenticated_user_can_retrieve_request(self):
        response = self.client.get(
            f"/api/requests/{self.request.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.request.id)

    def test_filter_requests_by_priority(self):
        response = self.client.get(
            "/api/requests/?priority=HIGH"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_invalid_filter_returns_no_matching_requests(self):
        response = self.client.get(
            "/api/requests/?priority=URGENT"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)