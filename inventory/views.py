from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AvailabilityForm, BookingForm
from .models import Booking, EquipmentType, EquipmentUnit
from .services import ACTIVE_BOOKING_STATUSES, available_units
from django.conf import settings


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
    active_count = Booking.objects.filter(
        borrower=request.user,
        status__in=ACTIVE_BOOKING_STATUSES,
    ).count()
    form = BookingForm(request.POST or None)
    if request.method == "POST":
        # Populate the ModelChoiceField before validation so a submitted unit must be real.
        start = request.POST.get("start_date")
        due = request.POST.get("due_date")
        if start and due:
            try:
                from datetime import date
                start_date = date.fromisoformat(start)
                due_date = date.fromisoformat(due)
                form.set_available_units(
                    EquipmentUnit.objects.select_related("equipment_type").order_by("asset_tag")
                )
            except ValueError:
                pass

        if active_count >= settings.MAX_CONCURRENT_BOOKINGS:
            form.add_error(None, f"You already have {settings.MAX_CONCURRENT_BOOKINGS} active bookings. Return or cancel one before booking another item.")
        elif form.is_valid():
            booking = form.save(commit=False)
            unit = booking.equipment_unit
            if booking not in Booking.objects.none():
                pass
            with transaction.atomic():
                if not available_units(unit.equipment_type, booking.start_date, booking.due_date).filter(pk=unit.pk).exists():
                    form.add_error("equipment_unit", "This unit is not available for the selected dates.")
                else:
                    booking.borrower = request.user
                    booking.deposit_charged = unit.equipment_type.deposit_amount
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
    cutoff = today + timedelta(days=2)
    bookings = list(
        Booking.objects.filter(
            status=Booking.Status.CHECKED_OUT,
            due_date__lte=cutoff,
        ).select_related("borrower", "equipment_unit", "equipment_unit__equipment_type").order_by("due_date", "id")
    )
    for booking in bookings:
        booking.days_overdue = max(0, (today - booking.due_date).days)
    return render(request, "inventory/dashboard.html", {"bookings": bookings, "today": today})
