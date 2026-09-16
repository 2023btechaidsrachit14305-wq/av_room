from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta

from inventory.models import Booking


class Command(BaseCommand):
    help = "Send console/email reminders for bookings due tomorrow or overdue."

    def handle(self, *args, **options):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        bookings = Booking.objects.filter(status=Booking.Status.CHECKED_OUT).filter(
            due_date__lte=tomorrow
        ).select_related("borrower", "equipment_unit", "equipment_unit__equipment_type")

        count = 0
        for booking in bookings:
            if booking.due_date == tomorrow:
                subject = "AV Room equipment due tomorrow"
                message = (
                    f"Hello {booking.borrower.get_full_name() or booking.borrower.username},\n\n"
                    f"Your {booking.equipment_unit.equipment_type.name} ({booking.equipment_unit.asset_tag}) "
                    f"is due tomorrow, {booking.due_date}.\nPlease return it on time."
                )
            else:
                days_overdue = max(0, (today - booking.due_date).days)
                subject = "AV Room equipment overdue"
                message = (
                    f"Hello {booking.borrower.get_full_name() or booking.borrower.username},\n\n"
                    f"Your {booking.equipment_unit.equipment_type.name} ({booking.equipment_unit.asset_tag}) "
                    f"is {days_overdue} day(s) overdue. The due date was {booking.due_date}.\n"
                    "Please return it as soon as possible."
                )

            if booking.borrower.email:
                send_mail(subject, message, None, [booking.borrower.email])
            self.stdout.write(message + "\n")
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Processed {count} reminder(s)."))
