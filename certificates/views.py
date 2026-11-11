from django.utils import timezone
from django.views.generic import ListView

from .models import STATUS_EXPIRED, STATUS_EXPIRING_SOON, Certificate

# Presentation only: maps a status label to a CSS badge class.
BADGE_CLASSES = {
    STATUS_EXPIRED: "badge-expired",
    STATUS_EXPIRING_SOON: "badge-soon",
}
DEFAULT_BADGE_CLASS = "badge-valid"


class CertificateListView(ListView):
    """Public list (intentional, see README), ordered by expiration date."""

    model = Certificate
    template_name = "certificates/certificate_list.html"
    context_object_name = "certificates"

    def get_queryset(self):
        return Certificate.objects.order_by("expiration_date", "domain_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # "Today" is evaluated once so every row is consistent.
        today = timezone.localdate()
        context["today"] = today
        context["rows"] = [
            {
                "certificate": cert,
                "days_left": cert.days_left(today),
                "status": (status := cert.status(today)),
                "badge_class": BADGE_CLASSES.get(status, DEFAULT_BADGE_CLASS),
            }
            for cert in context["certificates"]
        ]
        return context
