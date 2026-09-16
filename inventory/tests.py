from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Booking, EquipmentType, EquipmentUnit, TransferLog
from .services import available_units, return_booking, transfer_booking


class InventoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user("student", password="pass12345", email="student@example.com")
        self.other = User.objects.create_user("other", password="pass12345", email="other@example.com")
        self.staff = User.objects.create_user("staff", password="pass12345", is_staff=True)
        self.type = EquipmentType.objects.create(name="Test DSLR", category="DSLR", deposit_amount="1000.00", daily_late_fee="50.00")
        self.unit1 = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag="DSLR-T1")
        self.unit2 = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag="DSLR-T2")

    def make_booking(self, **kwargs):
        return Booking.objects.create(
            borrower=kwargs.get("user", self.student),
            equipment_unit=kwargs.get("unit", self.unit1),
            start_date=kwargs.get("start", date(2026, 10, 1)),
            due_date=kwargs.get("due", date(2026, 10, 4)),
            deposit_charged=self.type.deposit_amount,
            status=kwargs.get("status", Booking.Status.RESERVED),
        )

    def test_availability_overlap_and_non_overlap(self):
        self.make_booking()
        self.assertEqual(list(available_units(self.type, date(2026, 10, 2), date(2026, 10, 3))), [self.unit2])
        self.assertEqual(set(available_units(self.type, date(2026, 10, 4), date(2026, 10, 6))), {self.unit1, self.unit2})

    def test_valid_booking_and_double_booking_rejected(self):
        self.client.login(username="student", password="pass12345")
        response = self.client.post(reverse("create_booking"), {"equipment_unit": self.unit1.pk, "start_date": "2026-11-01", "due_date": "2026-11-04"})
        self.assertEqual(response.status_code, 302)
        duplicate = self.client.post(reverse("create_booking"), {"equipment_unit": self.unit1.pk, "start_date": "2026-11-02", "due_date": "2026-11-03"})
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, "not available for the selected dates")

    def test_max_concurrent_bookings_rejected(self):
        for index in range(settings.MAX_CONCURRENT_BOOKINGS):
            unit = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag=f"DSLR-M{index}")
            self.make_booking(unit=unit)
        self.client.login(username="student", password="pass12345")
        extra = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag="DSLR-MX")
        response = self.client.post(reverse("create_booking"), {"equipment_unit": extra.pk, "start_date": "2026-12-05", "due_date": "2026-12-07"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "active bookings")

    def test_on_time_return_full_refund(self):
        booking = self.make_booking(due=date(2026, 9, 20), status=Booking.Status.CHECKED_OUT)
        booking.equipment_unit.status = EquipmentUnit.Status.CHECKED_OUT
        booking.equipment_unit.save(update_fields=["status"])
        return_booking(booking, date(2026, 9, 20))
        self.assertEqual(booking.late_fee_charged, Decimal("0.00"))
        self.assertEqual(booking.refund_amount, Decimal("1000.00"))

    def test_late_return_fee_correct(self):
        self.type.daily_late_fee = Decimal("30.00")
        self.type.deposit_amount = Decimal("100.00")
        self.type.save(update_fields=["daily_late_fee", "deposit_amount"])
        booking = Booking.objects.create(borrower=self.student, equipment_unit=self.unit1, start_date=date(2026, 9, 18), due_date=date(2026, 9, 20), deposit_charged=Decimal("100.00"), status=Booking.Status.CHECKED_OUT)
        self.unit1.status = EquipmentUnit.Status.CHECKED_OUT
        self.unit1.save(update_fields=["status"])
        return_booking(booking, date(2026, 9, 23))
        self.assertEqual(booking.late_fee_charged, Decimal("90.00"))

    def test_very_late_return_fee_capped_at_deposit(self):
        self.type.daily_late_fee = Decimal("30.00")
        self.type.deposit_amount = Decimal("100.00")
        self.type.save(update_fields=["daily_late_fee", "deposit_amount"])
        booking = Booking.objects.create(borrower=self.student, equipment_unit=self.unit1, start_date=date(2026, 9, 18), due_date=date(2026, 9, 20), deposit_charged=Decimal("100.00"), status=Booking.Status.CHECKED_OUT)
        self.unit1.status = EquipmentUnit.Status.CHECKED_OUT
        self.unit1.save(update_fields=["status"])
        return_booking(booking, date(2026, 10, 20))
        self.assertEqual(booking.late_fee_charged, Decimal("100.00"))

    def test_transfer_checked_out_creates_log_and_preserves_window(self):
        booking = self.make_booking(status=Booking.Status.CHECKED_OUT)
        self.unit1.status = EquipmentUnit.Status.CHECKED_OUT
        self.unit1.save(update_fields=["status"])
        due = booking.due_date
        transfer_booking(booking, self.other, self.staff)
        booking.refresh_from_db()
        self.assertEqual(booking.borrower, self.other)
        self.assertEqual(booking.due_date, due)
        self.assertEqual(booking.status, Booking.Status.CHECKED_OUT)
        self.assertEqual(booking.equipment_unit.status, EquipmentUnit.Status.CHECKED_OUT)
        self.assertTrue(TransferLog.objects.filter(booking=booking, from_user=self.student, to_user=self.other, transferred_by=self.staff).exists())
        self.assertNotIn(self.unit1, available_units(self.type, booking.start_date, booking.due_date))

    def test_reserved_transfer_rejected(self):
        with self.assertRaises(ValidationError):
            transfer_booking(self.make_booking(status=Booking.Status.RESERVED), self.other, self.staff)

    def test_transfer_target_at_max_rejected(self):
        for index in range(settings.MAX_CONCURRENT_BOOKINGS):
            unit = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag=f"DSLR-X{index}")
            self.make_booking(user=self.other, unit=unit)
        booking = self.make_booking(status=Booking.Status.CHECKED_OUT)
        with self.assertRaises(ValidationError):
            transfer_booking(booking, self.other, self.staff)


class APIEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.student = User.objects.create_user("api_student", password="pass12345")
        self.staff = User.objects.create_user("api_staff", password="pass12345", is_staff=True)
        self.other = User.objects.create_user("api_other", password="pass12345")
        self.type = EquipmentType.objects.create(name="API DSLR", category="DSLR", deposit_amount="1200.00", daily_late_fee="60.00")
        self.unit = EquipmentUnit.objects.create(equipment_type=self.type, asset_tag="API-001")
        self.client = APIClient()

    def test_api_smoke_all_endpoints(self):
        response = self.client.get(reverse("api_availability"), {"category": "DSLR", "start_date": "2026-10-01", "end_date": "2026-10-05"})
        self.assertEqual(response.status_code, 200)
        self.client.force_login(self.student)
        response = self.client.post(reverse("api_bookings"), {"equipment_unit": self.unit.pk, "start_date": "2026-10-01", "due_date": "2026-10-05"}, format="json")
        self.assertEqual(response.status_code, 201)
        booking_id = response.json()["id"]
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse("api_checkout", kwargs={"pk": booking_id}), {}, format="json").status_code, 200)
        self.assertEqual(self.client.get(reverse("api_dashboard")).status_code, 200)
        self.assertEqual(self.client.post(reverse("api_transfer", kwargs={"pk": booking_id}), {"new_borrower_id": self.other.pk}, format="json").status_code, 200)
        returned = self.client.post(reverse("api_return", kwargs={"pk": booking_id}), {}, format="json")
        self.assertEqual(returned.status_code, 200)
        self.assertIn("late_fee", returned.json())
        self.assertIn("refund_amount", returned.json())
