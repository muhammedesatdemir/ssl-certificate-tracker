from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import (
    EXPIRY_WARNING_DAYS,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
    STATUS_VALID,
    Certificate,
)


class StatusListFilter(admin.SimpleListFilter):
    """Filter by computed status.

    The status itself is computed by Certificate.status(); a database filter
    cannot call Python, so this translates the same thresholds
    (EXPIRY_WARNING_DAYS) into date ranges. Tests assert both stay in sync.
    """

    title = "durum"
    parameter_name = "durum"

    def lookups(self, request, model_admin):
        return [
            ("expired", STATUS_EXPIRED),
            ("soon", STATUS_EXPIRING_SOON),
            ("valid", STATUS_VALID),
        ]

    def queryset(self, request, queryset):
        today = timezone.localdate()
        limit = today + timedelta(days=EXPIRY_WARNING_DAYS)
        if self.value() == "expired":
            return queryset.filter(expiration_date__lt=today)
        if self.value() == "soon":
            return queryset.filter(expiration_date__gte=today, expiration_date__lte=limit)
        if self.value() == "valid":
            return queryset.filter(expiration_date__gt=limit)
        return queryset


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "domain_name",
        "customer_name",
        "expiration_date",
        "days_left_display",
        "status_display",
    )
    list_filter = (StatusListFilter, "expiration_date")
    search_fields = ("domain_name", "customer_name")
    ordering = ("expiration_date",)

    @admin.display(description="Kalan gün", ordering="expiration_date")
    def days_left_display(self, obj):
        return obj.days_left()

    @admin.display(description="Durum", ordering="expiration_date")
    def status_display(self, obj):
        return obj.status()
