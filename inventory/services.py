from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from .models import Booking, EquipmentType, EquipmentUnit, TransferLog


ACTIVE_BOOKING_STATUSES = [Booking.Status.RESERVED, Booking.Status.CHECKED_OUT]


def available_units(equipment_type: EquipmentType, start_date, end_date) -> QuerySet[EquipmentUnit]:
    """Return units with no active booking overlapping the requested range."""
    if start_date >= end_date:
        return EquipmentUnit.objects.none()

    overlapping = Booking.objects.filter(
        start_date__lt=end_date,
        due_date__gt=start_date,
        status__in=ACTIVE_BOOKING_STATUSES,
    )
    return (
        EquipmentUnit.objects.filter(equipment_type=equipment_type)
        .exclude(bookings__in=overlapping)
        .select_related("equipment_type")
        .order_by("asset_tag")
    )


def create_booking(borrower, equipment_unit, start_date, due_date) -> Booking:
    active_count = Booking.objects.filter(
        borrower=borrower,
        status__in=ACTIVE_BOOKING_STATUSES,
    ).count()
    if active_count >= settings.MAX_CONCURRENT_BOOKINGS:
        raise ValidationError(
            f"You already have {settings.MAX_CONCURRENT_BOOKINGS} active bookings. "
            "Return or cancel one before booking another item."
        )

    if not available_units(
        equipment_unit.equipment_type, start_date, due_date
    ).filter(pk=equipment_unit.pk).exists():
        raise ValidationError("This unit is not available for the selected dates.")

    with transaction.atomic():
        return Booking.objects.create(
            borrower=borrower,
            equipment_unit=equipment_unit,
            start_date=start_date,
            due_date=due_date,
            deposit_charged=equipment_unit.equipment_type.deposit_amount,
            late_fee_charged=0,
            status=Booking.Status.RESERVED,
        )


def checkout_booking(booking: Booking) -> Booking:
    if booking.status != Booking.Status.RESERVED:
        raise ValidationError("Only reserved bookings can be checked out.")
    with transaction.atomic():
        booking.status = Booking.Status.CHECKED_OUT
        booking.equipment_unit.status = EquipmentUnit.Status.CHECKED_OUT
        booking.equipment_unit.save(update_fields=["status"])
        booking.save(update_fields=["status"])
    return booking


def return_booking(booking: Booking, returned_date=None) -> Booking:
    if booking.status != Booking.Status.CHECKED_OUT:
        raise ValidationError("Only checked-out bookings can be returned.")
    returned_date = returned_date or timezone.localdate()
    late_days = max(0, (returned_date - booking.due_date).days)
    late_fee = min(
        booking.deposit_charged,
        late_days * booking.equipment_unit.equipment_type.daily_late_fee,
    )
    with transaction.atomic():
        booking.returned_date = returned_date
        booking.late_fee_charged = late_fee
        booking.status = Booking.Status.RETURNED
        booking.equipment_unit.status = EquipmentUnit.Status.AVAILABLE
        booking.equipment_unit.save(update_fields=["status"])
        booking.save(update_fields=["returned_date", "late_fee_charged", "status"])
    return booking


def transfer_booking(booking: Booking, new_borrower, performed_by=None) -> Booking:
    """Transfer a live loan without changing its date window or unit status.

    Availability is deliberately not checked or changed: the EquipmentUnit stays
    checked_out throughout the transfer, so the existing availability window does
    not open up and no overlap calculation is needed.
    """
    if booking.status != Booking.Status.CHECKED_OUT:
        raise ValidationError("Only checked-out bookings can be transferred.")
    if new_borrower == booking.borrower:
        raise ValidationError("The new borrower must be different from the current borrower.")

    active_count = Booking.objects.filter(
        borrower=new_borrower,
        status__in=ACTIVE_BOOKING_STATUSES,
    ).count()
    if active_count >= settings.MAX_CONCURRENT_BOOKINGS:
        raise ValidationError(
            f"The new borrower already has {settings.MAX_CONCURRENT_BOOKINGS} active bookings."
        )

    with transaction.atomic():
        from_user = booking.borrower
        booking.borrower = new_borrower
        booking.save(update_fields=["borrower"])
        TransferLog.objects.create(
            booking=booking,
            from_user=from_user,
            to_user=new_borrower,
            transferred_by=performed_by,
        )
    return booking
