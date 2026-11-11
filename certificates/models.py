from datetime import date

from django.db import models
from django.utils import timezone

# Single source of truth for the warning window (see CLAUDE.md).
EXPIRY_WARNING_DAYS = 30

# Status labels are defined once and reused by admin, templates and tests.
STATUS_EXPIRED = "Süresi Dolmuş"
STATUS_EXPIRING_SOON = "Yakında Dolacak"
STATUS_VALID = "Geçerli"


class Certificate(models.Model):
    domain_name = models.CharField("alan adı", max_length=255)
    customer_name = models.CharField("müşteri adı", max_length=255)
    # Calendar day in Europe/Istanbul. The certificate is valid through the
    # end of this day, so expiration_date == today means 0 days left.
    expiration_date = models.DateField("bitiş tarihi", db_index=True)

    class Meta:
        ordering = ["expiration_date"]
        # A renewal may overlap the old certificate, so the domain alone is
        # not unique; the (domain, date) pair is.
        unique_together = [("domain_name", "expiration_date")]
        verbose_name = "sertifika"
        verbose_name_plural = "sertifikalar"

    def __str__(self):
        return f"{self.domain_name} ({self.expiration_date})"

    def _normalize_domain(self):
        self.domain_name = (self.domain_name or "").strip().lower()

    def clean(self):
        # Runs before validate_unique() in ModelForm/admin validation, so the
        # uniqueness check sees the normalized value, not the raw input.
        self._normalize_domain()
        super().clean()

    def save(self, *args, **kwargs):
        # Covers saves that bypass form validation (shell, seed, fixtures).
        self._normalize_domain()
        super().save(*args, **kwargs)

    @staticmethod
    def _resolve_today(today: date | None) -> date:
        return timezone.localdate() if today is None else today

    def days_left(self, today: date | None = None) -> int:
        """Whole days until expiration; negative once expired."""
        return (self.expiration_date - self._resolve_today(today)).days

    def status(self, today: date | None = None) -> str:
        days = self.days_left(today)
        if days < 0:
            return STATUS_EXPIRED
        if days <= EXPIRY_WARNING_DAYS:
            return STATUS_EXPIRING_SOON
        return STATUS_VALID
