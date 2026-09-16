from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.forms import RequestForm
from core.models import Partner, Request


class RequestFormTest(TestCase):
    """
    Tests the two validation rules from spec §5.3:
      1. target_date cannot be in the past
      2. no two unfinished requests for the same partner+service+direction
    """

    @classmethod
    def setUpTestData(cls):
        cls.partner = Partner.objects.create(
            code="PT-TE-001",
            name="Test Telecom",
            country="Testland",
            region="EMEA",
            active=True,
        )
        cls.requester = User.objects.create_user(username="test_requester")

    def _valid_data(self, **overrides):
        data = {
            "partner": self.partner.id,
            "service": "DATA_5G",
            "direction": "OUTBOUND",
            "priority": "NORMAL",
            "target_date": (timezone.now().date() + timedelta(days=10)).isoformat(),
            "description": "Enable 5G data for Test Telecom",
            # RequestForm now carries a required hidden 'version' field
            # (added for the two-people-editing protection) — needs a
            # value here or the form is correctly rejected as incomplete.
            "version": 1,
        }
        data.update(overrides)
        return data

    # --- Rule 1: target date cannot be in the past ---

    def test_valid_form_with_future_date_is_valid(self):
        form = RequestForm(data=self._valid_data())
        self.assertTrue(form.is_valid())

    def test_past_target_date_is_rejected(self):
        past_date = (timezone.now().date() - timedelta(days=1)).isoformat()
        form = RequestForm(data=self._valid_data(target_date=past_date))
        self.assertFalse(form.is_valid())
        self.assertIn("target_date", form.errors)

    def test_todays_date_is_allowed(self):
        # Today isn't "in the past" — only dates strictly before today
        # should be rejected.
        today = timezone.now().date().isoformat()
        form = RequestForm(data=self._valid_data(target_date=today))
        self.assertTrue(form.is_valid())

    # --- Rule 2: no duplicate unfinished partner+service+direction ---

    def test_duplicate_unfinished_request_is_rejected(self):
        Request.objects.create(
            partner=self.partner,
            service="DATA_5G",
            direction="OUTBOUND",
            target_date=timezone.now().date() + timedelta(days=5),
            requester=self.requester,
            current_step="TESTING",
        )
        form = RequestForm(data=self._valid_data())
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)

    def test_duplicate_is_allowed_if_existing_one_is_live(self):
        Request.objects.create(
            partner=self.partner,
            service="DATA_5G",
            direction="OUTBOUND",
            target_date=timezone.now().date() + timedelta(days=5),
            requester=self.requester,
            current_step="LIVE",
        )
        form = RequestForm(data=self._valid_data())
        self.assertTrue(form.is_valid())

    def test_duplicate_is_allowed_if_existing_one_is_rejected(self):
        Request.objects.create(
            partner=self.partner,
            service="DATA_5G",
            direction="OUTBOUND",
            target_date=timezone.now().date() + timedelta(days=5),
            requester=self.requester,
            current_step="REJECTED",
        )
        form = RequestForm(data=self._valid_data())
        self.assertTrue(form.is_valid())

    def test_different_direction_is_not_a_duplicate(self):
        Request.objects.create(
            partner=self.partner,
            service="DATA_5G",
            direction="INBOUND",
            target_date=timezone.now().date() + timedelta(days=5),
            requester=self.requester,
            current_step="TESTING",
        )
        form = RequestForm(data=self._valid_data(direction="OUTBOUND"))
        self.assertTrue(form.is_valid())

    def test_editing_existing_request_does_not_flag_itself_as_duplicate(self):
        existing = Request.objects.create(
            partner=self.partner,
            service="DATA_5G",
            direction="OUTBOUND",
            target_date=timezone.now().date() + timedelta(days=5),
            requester=self.requester,
            current_step="TESTING",
        )
        form = RequestForm(data=self._valid_data(), instance=existing)
        self.assertTrue(form.is_valid())