from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from .models import (
    EXPIRY_WARNING_DAYS,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
    STATUS_VALID,
    Certificate,
)

# A fixed "today" is passed explicitly; tests never depend on the real clock.
TODAY = date(2026, 6, 15)


def make_cert(offset_days, domain="example.com"):
    """Unsaved certificate expiring `offset_days` from TODAY."""
    return Certificate(
        domain_name=domain,
        customer_name="Test Müşteri",
        expiration_date=TODAY + timedelta(days=offset_days),
    )


class StatusBoundaryTests(SimpleTestCase):
    def test_warning_window_constant_is_30(self):
        self.assertEqual(EXPIRY_WARNING_DAYS, 30)

    def test_yesterday_is_expired(self):
        cert = make_cert(-1)
        self.assertEqual(cert.days_left(TODAY), -1)
        self.assertEqual(cert.status(TODAY), STATUS_EXPIRED)

    def test_today_is_expiring_soon_with_zero_days_left(self):
        cert = make_cert(0)
        self.assertEqual(cert.days_left(TODAY), 0)
        self.assertEqual(cert.status(TODAY), STATUS_EXPIRING_SOON)

    def test_29_days_is_expiring_soon(self):
        cert = make_cert(EXPIRY_WARNING_DAYS - 1)
        self.assertEqual(cert.days_left(TODAY), 29)
        self.assertEqual(cert.status(TODAY), STATUS_EXPIRING_SOON)

    def test_exactly_30_days_is_still_expiring_soon(self):
        cert = make_cert(EXPIRY_WARNING_DAYS)
        self.assertEqual(cert.days_left(TODAY), 30)
        self.assertEqual(cert.status(TODAY), STATUS_EXPIRING_SOON)

    def test_31_days_is_valid(self):
        cert = make_cert(EXPIRY_WARNING_DAYS + 1)
        self.assertEqual(cert.days_left(TODAY), 31)
        self.assertEqual(cert.status(TODAY), STATUS_VALID)

    def test_far_future_is_valid(self):
        self.assertEqual(make_cert(3650).status(TODAY), STATUS_VALID)

    def test_far_past_is_expired_with_negative_days(self):
        cert = make_cert(-3650)
        self.assertEqual(cert.days_left(TODAY), -3650)
        self.assertEqual(cert.status(TODAY), STATUS_EXPIRED)

    def test_default_today_uses_real_local_date(self):
        # today=None must fall back to timezone.localdate(); certs in the
        # year 2999 / 2000 give a stable result whenever the suite runs.
        far_future = Certificate(
            domain_name="a.com", customer_name="x", expiration_date=date(2999, 1, 1)
        )
        far_past = Certificate(
            domain_name="a.com", customer_name="x", expiration_date=date(2000, 1, 1)
        )
        self.assertEqual(far_future.status(), STATUS_VALID)
        self.assertEqual(far_past.status(), STATUS_EXPIRED)


class DomainNormalizationTests(TestCase):
    def test_save_strips_and_lowercases_domain(self):
        cert = Certificate.objects.create(
            domain_name="  Example.COM  ",
            customer_name="Müşteri",
            expiration_date=TODAY,
        )
        cert.refresh_from_db()
        self.assertEqual(cert.domain_name, "example.com")

    def test_clean_normalizes_domain(self):
        cert = make_cert(5, domain="  WWW.Example.Com ")
        cert.clean()
        self.assertEqual(cert.domain_name, "www.example.com")

    def test_form_validation_catches_case_and_whitespace_duplicate(self):
        Certificate.objects.create(
            domain_name="example.com", customer_name="A", expiration_date=TODAY
        )
        duplicate = Certificate(
            domain_name=" Example.COM ", customer_name="B", expiration_date=TODAY
        )
        # full_clean() is what ModelForm/admin runs: clean() -> validate_unique().
        with self.assertRaises(ValidationError):
            duplicate.full_clean()


class UniquenessTests(TestCase):
    def test_same_domain_different_date_is_allowed(self):
        Certificate.objects.create(
            domain_name="example.com", customer_name="A", expiration_date=TODAY
        )
        Certificate.objects.create(
            domain_name="example.com",
            customer_name="A",
            expiration_date=TODAY + timedelta(days=365),
        )
        self.assertEqual(Certificate.objects.filter(domain_name="example.com").count(), 2)

    def test_same_domain_and_date_is_rejected_at_db_level(self):
        Certificate.objects.create(
            domain_name="example.com", customer_name="A", expiration_date=TODAY
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Certificate.objects.create(
                domain_name="EXAMPLE.com", customer_name="B", expiration_date=TODAY
            )


class OrderingTests(TestCase):
    def test_default_ordering_is_by_expiration_date(self):
        later = Certificate.objects.create(
            domain_name="b.com", customer_name="x", expiration_date=TODAY + timedelta(days=10)
        )
        earlier = Certificate.objects.create(
            domain_name="a.com", customer_name="x", expiration_date=TODAY - timedelta(days=10)
        )
        self.assertEqual(list(Certificate.objects.all()), [earlier, later])


# --- View and admin tests -------------------------------------------------
# These go through the real request cycle, which uses timezone.localdate(), so
# fixtures are built relative to it instead of the fixed TODAY above.

from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402

from .admin import CertificateAdmin  # noqa: E402


def make_saved(offset_days, domain):
    return Certificate.objects.create(
        domain_name=domain,
        customer_name="Müşteri",
        expiration_date=timezone.localdate() + timedelta(days=offset_days),
    )


class CertificateListViewTests(TestCase):
    def test_list_page_is_public_and_ok(self):
        response = self.client.get(reverse("certificates:list"))
        self.assertEqual(response.status_code, 200)

    def test_empty_state_message(self):
        response = self.client.get(reverse("certificates:list"))
        self.assertContains(response, "Henüz sertifika kaydı yok")

    def test_rows_are_ordered_by_expiration_date(self):
        make_saved(100, "valid.com")
        make_saved(-5, "expired.com")
        make_saved(10, "soon.com")
        response = self.client.get(reverse("certificates:list"))
        domains = [row["certificate"].domain_name for row in response.context["rows"]]
        self.assertEqual(domains, ["expired.com", "soon.com", "valid.com"])

    def test_shows_status_text_days_left_and_badge_class(self):
        make_saved(-5, "expired.com")
        make_saved(0, "today.com")
        make_saved(100, "valid.com")
        response = self.client.get(reverse("certificates:list"))
        rows = {r["certificate"].domain_name: r for r in response.context["rows"]}

        self.assertEqual(rows["expired.com"]["status"], STATUS_EXPIRED)
        self.assertEqual(rows["expired.com"]["days_left"], -5)
        self.assertEqual(rows["expired.com"]["badge_class"], "badge-expired")
        self.assertEqual(rows["today.com"]["status"], STATUS_EXPIRING_SOON)
        self.assertEqual(rows["today.com"]["days_left"], 0)
        self.assertEqual(rows["today.com"]["badge_class"], "badge-soon")
        self.assertEqual(rows["valid.com"]["status"], STATUS_VALID)
        self.assertEqual(rows["valid.com"]["badge_class"], "badge-valid")

        for label in (STATUS_EXPIRED, STATUS_EXPIRING_SOON, STATUS_VALID):
            self.assertContains(response, label)


class CertificateAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            "admin", "admin@example.com", "pass12345"
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_changelist_shows_status_and_days_left(self):
        make_saved(-3, "expired.com")
        response = self.client.get(reverse("admin:certificates_certificate_changelist"))
        self.assertContains(response, "expired.com")
        self.assertContains(response, STATUS_EXPIRED)
        self.assertContains(response, "-3")

    def test_list_display_and_search_config(self):
        self.assertIn("status_display", CertificateAdmin.list_display)
        self.assertIn("days_left_display", CertificateAdmin.list_display)
        self.assertEqual(CertificateAdmin.search_fields, ("domain_name", "customer_name"))

    def test_search_finds_by_domain_and_customer(self):
        make_saved(5, "findme.com")
        make_saved(5, "other.com")
        url = reverse("admin:certificates_certificate_changelist")
        response = self.client.get(url, {"q": "findme"})
        self.assertContains(response, "findme.com")
        self.assertNotContains(response, "other.com")

    def test_status_filter_matches_model_status(self):
        # The DB-level filter and Certificate.status() must agree at every boundary.
        offsets = {-1: "expired", 0: "soon", 29: "soon", 30: "soon", 31: "valid"}
        for offset in offsets:
            make_saved(offset, f"d{offset + 5}.com")
        url = reverse("admin:certificates_certificate_changelist")
        labels = {"expired": STATUS_EXPIRED, "soon": STATUS_EXPIRING_SOON, "valid": STATUS_VALID}
        for key, label in labels.items():
            response = self.client.get(url, {"durum": key})
            shown = list(response.context["cl"].queryset)
            self.assertTrue(shown, key)
            for cert in shown:
                self.assertEqual(cert.status(), label)
            expected = [o for o, k in offsets.items() if k == key]
            self.assertEqual(len(shown), len(expected), key)
