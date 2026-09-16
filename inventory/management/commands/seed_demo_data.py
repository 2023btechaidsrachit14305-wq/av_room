from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from inventory.models import Booking, EquipmentType, EquipmentUnit


class Command(BaseCommand):
    help = "Create repeatable demo equipment, students, and bookings."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        demo_users = [
            ("demo_student1", "demo1@example.com", "Demo Student One"),
            ("demo_student2", "demo2@example.com", "Demo Student Two"),
            ("demo_student3", "demo3@example.com", "Demo Student Three"),
        ]
        users = []
        for username, email, full_name in demo_users:
            user, created = User.objects.get_or_create(username=username, defaults={"email": email})
            user.email = email
            first, *last = full_name.split()
            user.first_name = first
            user.last_name = " ".join(last)
            if created:
                user.set_password("demo12345")
            user.save()
            users.append(user)

        specs = [
            ("Canon EOS 1500D", EquipmentType.Category.DSLR, Decimal("5000.00"), Decimal("100.00")),
            ("Epson EB-X06", EquipmentType.Category.PROJECTOR, Decimal("4000.00"), Decimal("150.00")),
            ("Shure SM58", EquipmentType.Category.MIC, Decimal("1500.00"), Decimal("75.00")),
            ("Manfrotto Tripod", EquipmentType.Category.TRIPOD, Decimal("2000.00"), Decimal("80.00")),
        ]

        types = {}
        for name, category, deposit, fee in specs:
            equipment_type, _ = EquipmentType.objects.get_or_create(
                name=name,
                defaults={"category": category, "deposit_amount": deposit, "daily_late_fee": fee},
            )
            equipment_type.category = category
            equipment_type.deposit_amount = deposit
            equipment_type.daily_late_fee = fee
            equipment_type.save()
            types[category] = equipment_type

        units = {}
        for category, equipment_type in types.items():
            for number in range(1, 4):
                tag = f"{category.upper()}-{number:03d}"
                unit, _ = EquipmentUnit.objects.get_or_create(
                    asset_tag=tag,
                    defaults={"equipment_type": equipment_type, "status": EquipmentUnit.Status.AVAILABLE},
                )
                unit.equipment_type = equipment_type
                unit.status = EquipmentUnit.Status.AVAILABLE
                unit.save()
                units[(category, number)] = unit

        Booking.objects.filter(borrower__username__startswith="demo_student").delete()
        today = timezone.localdate()

        on_time = Booking.objects.create(
            borrower=users[0],
            equipment_unit=units[(EquipmentType.Category.DSLR, 1)],
            start_date=today - timedelta(days=1),
            due_date=today + timedelta(days=1),
            deposit_charged=types[EquipmentType.Category.DSLR].deposit_amount,
            status=Booking.Status.CHECKED_OUT,
        )
        overdue = Booking.objects.create(
            borrower=users[1],
            equipment_unit=units[(EquipmentType.Category.PROJECTOR, 1)],
            start_date=today - timedelta(days=5),
            due_date=today - timedelta(days=2),
            deposit_charged=types[EquipmentType.Category.PROJECTOR].deposit_amount,
            status=Booking.Status.CHECKED_OUT,
        )
        units[(EquipmentType.Category.DSLR, 1)].status = EquipmentUnit.Status.CHECKED_OUT
        units[(EquipmentType.Category.DSLR, 1)].save(update_fields=["status"])
        units[(EquipmentType.Category.PROJECTOR, 1)].status = EquipmentUnit.Status.CHECKED_OUT
        units[(EquipmentType.Category.PROJECTOR, 1)].save(update_fields=["status"])

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
        self.stdout.write(f"Users: {', '.join(user.username for user in users)} (password: demo12345)")
        self.stdout.write(f"Created bookings: #{on_time.pk} on-time, #{overdue.pk} overdue")
