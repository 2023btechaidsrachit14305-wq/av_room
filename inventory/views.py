from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AvailabilityForm, BookingForm
from .models import Booking, EquipmentType
from .services import ACTIVE_BOOKING_STATUSES, available_units, create_booking


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
def create_booking_view(request):
    form = BookingForm(request.POST or None)
    if form.is_valid():
        try:
            booking = create_booking(
                request.user,
                form.cleaned_data["equipment_unit"],
                form.cleaned_data["start_date"],
                form.cleaned_data["due_date"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
        else:
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
