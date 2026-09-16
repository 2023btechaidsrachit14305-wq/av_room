from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Booking, EquipmentType, EquipmentUnit
from .services import available_units


class AvailabilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="student")
        self.type = EquipmentType.objects.create(
            name="Test DSLR", category=EquipmentType.Category.DSLR,
            deposit_amount="1000.00", daily_late_fee="50.00",
        )
        self.unit1 = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag="DSLR-T1")
        self.unit2 = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag="DSLR-T2")
        self.start = date(2026, 9, 19)
        self.end = date(2026, 9, 22)
        Booking.objects.create(
            borrower=self.user, equipment_unit=self.unit1,
            start_date=self.start, due_date=self.end,
            deposit_charged="1000.00", status=Booking.Status.RESERVED,
        )

    def test_overlapping_range_returns_one_free_unit(self):
        free = available_units(self.type, date(2026, 9, 20), date(2026, 9, 21))
        self.assertEqual(list(free), [self.unit2])

    def test_non_overlapping_range_returns_both_units(self):
        free = available_units(self.type, date(2026, 9, 22), date(2026, 9, 24))
        self.assertEqual(set(free), {self.unit1, self.unit2})
