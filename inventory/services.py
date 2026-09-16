from django.db.models import QuerySet

from .models import Booking, EquipmentType, EquipmentUnit


ACTIVE_BOOKING_STATUSES = [Booking.Status.RESERVED, Booking.Status.CHECKED_OUT]


def available_units(
    equipment_type: EquipmentType,
    start_date,
    end_date,
) -> QuerySet[EquipmentUnit]:
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
