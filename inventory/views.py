from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.conf import settings

from .forms import AvailabilityForm, BookingForm
from .models import Booking, EquipmentType, EquipmentUnit
from .services import ACTIVE_BOOKING_STATUSES, available_units


def availability(request):
    form = AvailabilityForm(request.GET or None)
    results = []
    if form.is_valid():
        start = form.cleaned_data["start_date"]
        end = form.cleaned_data["end_date"]
        category = form.cleaned_data.get("category")
        types = EquipmentType.objects.all()
        if category:
            types = types.filter(category=category)
        for equipment_type in types:
            units = available_units(equipment_type, start, end)
            results.append({"equipment_type": equipment_type, "units": units, "count": units.count()})
    return render(request, "inventory/availability.html", {"form": form, "results": results})


@login_required
def create_booking(request):
    form = BookingForm(request.POST or None)
    if form.is_valid():
        booking = form.save(commit=False)
        if Booking.objects.filter(borrower=request.user, status__in=ACTIVE_BOOKING_STATUSES).count() >= settings.MAX_CONCURRENT_BOOKINGS:
            form.add_error(None, f"You already have {settings.MAX_CONCURRENT_BOOKINGS} active bookings. Return or cancel one before booking another item.")
        elif not available_units(booking.equipment_unit.equipment_type, booking.start_date, booking.due_date).filter(pk=booking.equipment_unit_id).exists():
            form.add_error("equipment_unit", "This unit is not available for the selected dates.")
        else:
            with transaction.atomic():
                booking.borrower = request.user
                booking.deposit_charged = booking.equipment_unit.equipment_type.deposit_amount
                booking.late_fee_charged = 0
                booking.status = Booking.Status.RESERVED
                booking.save()
            messages.success(request, "Booking reserved successfully.")
            return redirect("booking_confirmation", pk=booking.pk)
    return render(request, "inventory/booking_form.html", {"form": form})


@login_required
def booking_confirmation(request, pk):
    booking = get_object_or_404(Booking, pk=pk, borrower=request.user)
    return render(request, "inventory/booking_confirmation.html", {"booking": booking})


@user_passes_test(lambda user: user.is_staff)
def dashboard(request):
    today = timezone.localdate()
    bookings = list(
        Booking.objects.filter(
            status=Booking.Status.CHECKED_OUT,
            due_date__lte=today + timedelta(days=2),
        ).select_related("borrower", "equipment_unit", "equipment_unit__equipment_type").order_by("due_date", "id")
    )
    for booking in bookings:
        booking.days_overdue = max(0, (today - booking.due_date).days)
    return render(request, "inventory/dashboard.html", {"bookings": bookings, "today": today})
