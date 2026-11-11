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
