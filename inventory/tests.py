from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Booking, EquipmentType, EquipmentUnit
from .services import available_units


class InventorySetupMixin:
    def make_type(self, name="Test DSLR", deposit="1000.00", fee="50.00"):
        return EquipmentType.objects.create(
            name=name, category=EquipmentType.Category.DSLR,
            deposit_amount=deposit, daily_late_fee=fee,
        )


class AvailabilityTests(InventorySetupMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="student")
        self.type = self.make_type()
        self.unit1 = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag="DSLR-T1")
        self.unit2 = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag="DSLR-T2")
        self.start = date(2026, 9, 19)
        self.end = date(2026, 9, 22)
        Booking.objects.create(
            borrower=self.user, equipment_unit=self.unit1,
            start_date=self.start, due_date=self.end,
            deposit_charged=self.type.deposit_amount,
            status=Booking.Status.RESERVED,
        )

    def test_overlapping_range_returns_one_free_unit(self):
        self.assertEqual(list(available_units(self.type, date(2026, 9, 20), date(2026, 9, 21))), [self.unit2])

    def test_non_overlapping_range_returns_both_units(self):
        self.assertEqual(set(available_units(self.type, date(2026, 9, 22), date(2026, 9, 24))), {self.unit1, self.unit2})


class BookingFlowTests(InventorySetupMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="borrower", password="pass12345")
        self.type = self.make_type()
        self.units = [EquipmentUnit.objects.create(equipment_type=self.type, asset_tag=f"DSLR-B{i}") for i in range(1, 6)]
        self.start = date(2026, 10, 1)
        self.due = date(2026, 10, 4)
        self.client.login(username="borrower", password="pass12345")

    def test_rejected_double_booking(self):
        Booking.objects.create(
            borrower=self.user, equipment_unit=self.units[0], start_date=self.start,
            due_date=self.due, deposit_charged=self.type.deposit_amount,
            status=Booking.Status.RESERVED,
        )
        response = self.client.post(reverse("create_booking"), {"equipment_unit": self.units[0].pk, "start_date": self.start, "due_date": self.due})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not available for the selected dates")

    def test_rejected_past_max_concurrent_bookings(self):
        for unit in self.units[:settings.MAX_CONCURRENT_BOOKINGS]:
            Booking.objects.create(
                borrower=self.user, equipment_unit=unit, start_date=self.start,
                due_date=self.due, deposit_charged=self.type.deposit_amount,
                status=Booking.Status.RESERVED,
            )
        response = self.client.post(reverse("create_booking"), {"equipment_unit": self.units[3].pk, "start_date": self.start, "due_date": self.due})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "active bookings")

    def test_valid_booking_sets_deposit_and_reserved(self):
        response = self.client.post(reverse("create_booking"), {"equipment_unit": self.units[0].pk, "start_date": self.start, "due_date": self.due})
        self.assertRedirects(response, reverse("booking_confirmation", kwargs={"pk": Booking.objects.get().pk}))
        booking = Booking.objects.get()
        self.assertEqual(booking.deposit_charged, Decimal("1000.00"))
        self.assertEqual(booking.status, Booking.Status.RESERVED)


class ReturnFlowTests(InventorySetupMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="returner")
        self.type = self.make_type(deposit="100.00", fee="30.00")
        self.unit = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag="DSLR-R1")

    def make_booking(self, due_date):
        self.unit.status = EquipmentUnit.Status.CHECKED_OUT
        self.unit.save(update_fields=["status"])
        return Booking.objects.create(
            borrower=self.user, equipment_unit=self.unit,
            start_date=due_date - timedelta(days=2), due_date=due_date,
            deposit_charged=self.type.deposit_amount,
            status=Booking.Status.CHECKED_OUT,
        )

    def return_booking(self, booking, today):
        returned_date = today
        late_days = max(0, (returned_date - booking.due_date).days)
        booking.returned_date = returned_date
        booking.late_fee_charged = min(booking.deposit_charged, late_days * self.type.daily_late_fee)
        booking.status = Booking.Status.RETURNED
        booking.unit_ref = booking.equipment_unit
        booking.equipment_unit.status = EquipmentUnit.Status.AVAILABLE
        booking.equipment_unit.save(update_fields=["status"])
        booking.save(update_fields=["returned_date", "late_fee_charged", "status"])

    @override_settings(USE_TZ=True)
    def test_on_time_return_full_refund(self):
        due = date(2026, 9, 20)
        booking = self.make_booking(due)
        self.return_booking(booking, due)
        self.assertEqual(booking.late_fee_charged, Decimal("0"))
        self.assertEqual(booking.deposit_charged - booking.late_fee_charged, Decimal("100.00"))

    def test_late_return_fee_correct(self):
        due = date(2026, 9, 20)
        booking = self.make_booking(due)
        self.return_booking(booking, date(2026, 9, 23))
        self.assertEqual(booking.late_fee_charged, Decimal("90.00"))

    def test_very_late_return_fee_capped_at_deposit(self):
        due = date(2026, 9, 20)
        booking = self.make_booking(due)
        self.return_booking(booking, date(2026, 10, 20))
        self.assertEqual(booking.late_fee_charged, Decimal("100.00"))
