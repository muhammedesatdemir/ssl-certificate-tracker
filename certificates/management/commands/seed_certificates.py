from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from certificates.models import Certificate

# (domain, customer, days from today). Reserved example domains only, so the
# command never touches real data. Together they cover every status/boundary.
SAMPLES = [
    ("expired.example.com", "Örnek Bankacılık A.Ş.", -10),   # Süresi Dolmuş
    ("today.example.com", "Örnek Lojistik Ltd.", 0),          # Yakında Dolacak (0 gün)
    ("soon.example.com", "Örnek Perakende A.Ş.", 15),         # Yakında Dolacak
    ("limit.example.com", "Örnek Sağlık Hiz.", 30),           # Yakında Dolacak (sınır)
    ("valid.example.com", "Örnek Yazılım Ltd.", 60),          # Geçerli
]


class Command(BaseCommand):
    help = "Insert sample certificates (relative to today) covering every status."

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        # Dates are relative to today, so a re-run on another day would add
        # duplicates. Refresh only the rows this command owns (seed domains).
        deleted, _ = Certificate.objects.filter(
            domain_name__in=[domain for domain, _, _ in SAMPLES]
        ).delete()

        for domain, customer, offset in SAMPLES:
            cert = Certificate.objects.create(
                domain_name=domain,
                customer_name=customer,
                expiration_date=today + timedelta(days=offset),
            )
            self.stdout.write(
                f"  {cert.domain_name:<22} {cert.expiration_date}  "
                f"{cert.days_left(today):>4} gün  {cert.status(today)}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(SAMPLES)} örnek sertifika eklendi (yenilenen eski örnek: {deleted})."
            )
        )
