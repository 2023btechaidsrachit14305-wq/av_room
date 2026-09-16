from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, EquipmentType, EquipmentUnit
from .serializers import BookingSerializer, EquipmentTypeSerializer, EquipmentUnitSerializer
from .services import (
    ACTIVE_BOOKING_STATUSES,
    available_units,
    checkout_booking,
    create_booking,
    return_booking,
    transfer_booking,
)


class AvailabilityAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        category = request.query_params.get("category", "")
        start = request.query_params.get("start_date")
        end = request.query_params.get("end_date")
        if not start or not end:
            return Response({"detail": "start_date and end_date are required."}, status=400)
        try:
            start_date = timezone.datetime.fromisoformat(start).date()
            end_date = timezone.datetime.fromisoformat(end).date()
        except ValueError:
            return Response({"detail": "Dates must use YYYY-MM-DD."}, status=400)
        if start_date >= end_date:
            return Response({"detail": "end_date must be after start_date."}, status=400)

        types = EquipmentType.objects.all()
        if category:
            types = types.filter(category=category)
        units = EquipmentUnit.objects.filter(equipment_type__in=types)
        blocked = Booking.objects.filter(
            start_date__lt=end_date,
            due_date__gt=start_date,
            status__in=ACTIVE_BOOKING_STATUSES,
        )
        free = units.exclude(bookings__in=blocked).select_related("equipment_type").order_by("asset_tag")
        return Response(EquipmentUnitSerializer(free, many=True).data)


class BookingCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        try:
            booking = create_booking(
                request.user,
                serializer.validated_data["equipment_unit"],
                serializer.validated_data["start_date"],
                serializer.validated_data["due_date"],
            )
        except ValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class StaffBookingActionAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk, action):
        booking = Booking.objects.select_related("equipment_unit__equipment_type", "borrower").get(pk=pk)
        try:
            if action == "checkout":
                checkout_booking(booking)
                return Response(BookingSerializer(booking).data)
            if action == "return":
                return_booking(booking)
                return Response({
                    "booking": BookingSerializer(booking).data,
                    "late_fee": str(booking.late_fee_charged),
                    "refund_amount": str(booking.refund_amount),
                })
        except ValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)
        return Response({"detail": "Unknown action."}, status=404)


class TransferAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        booking = Booking.objects.select_related("borrower", "equipment_unit__equipment_type").get(pk=pk)
        try:
            new_borrower = get_user_model().objects.get(pk=request.data.get("new_borrower_id"))
            due_date = booking.due_date
            transfer_booking(booking, new_borrower, request.user)
        except get_user_model().DoesNotExist:
            return Response({"detail": "New borrower not found."}, status=400)
        except (TypeError, ValueError):
            return Response({"detail": "new_borrower_id is required."}, status=400)
        except ValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)
        return Response({"booking": BookingSerializer(booking).data, "due_date_unchanged": due_date.isoformat()})


class DashboardAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        today = timezone.localdate()
        bookings = Booking.objects.filter(
            status=Booking.Status.CHECKED_OUT,
            due_date__lte=today + timezone.timedelta(days=2),
        ).select_related("borrower", "equipment_unit__equipment_type").order_by("due_date", "id")
        data = BookingSerializer(bookings, many=True).data
        for item, booking in zip(data, bookings):
            item["days_overdue"] = max(0, (today - booking.due_date).days)
        return Response(data)
