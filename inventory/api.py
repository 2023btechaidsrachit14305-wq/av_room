from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, EquipmentType, EquipmentUnit
from .serializers import BookingSerializer, EquipmentUnitSerializer
from .services import ACTIVE_BOOKING_STATUSES, checkout_booking, create_booking, return_booking, transfer_booking


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
def auth_me(request):
    if not request.user.is_authenticated:
        return Response({"authenticated": False, "user": None})
    return Response({"authenticated": True, "user": user_payload(request.user)})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_login(request):
    username = str(request.data.get("username", "")).strip()
    password = request.data.get("password", "")
    if not username or not password:
        return Response({"detail": "Username and password are required."}, status=400)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"detail": "Invalid username or password."}, status=400)
    if not user.is_active:
        return Response({"detail": "This account is inactive."}, status=403)
    login(request, user)
    return Response({"authenticated": True, "user": user_payload(user)})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def auth_register(request):
    User = get_user_model()
    username = str(request.data.get("username", "")).strip().lower()
    password = request.data.get("password", "")
    first_name = str(request.data.get("first_name", "")).strip()
    last_name = str(request.data.get("last_name", "")).strip()
    email = str(request.data.get("email", "")).strip()
    if not username or not password or not first_name:
        return Response({"detail": "First name, username and password are required."}, status=400)
    if len(password) < 8:
        return Response({"detail": "Password must be at least 8 characters."}, status=400)
    if User.objects.filter(username=username).exists():
        return Response({"detail": "That username is already taken."}, status=400)
    if email and User.objects.filter(email__iexact=email).exists():
        return Response({"detail": "That email is already registered."}, status=400)
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    login(request, user)
    return Response({"authenticated": True, "user": user_payload(user)}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def auth_logout(request):
    logout(request)
    return Response({"authenticated": False})


class AvailabilityAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        category = request.query_params.get("category", "")
        start = request.query_params.get("start_date")
        end = request.query_params.get("end_date")
        if not start or not end:
            return Response({"detail": "Start date and end date are required."}, status=400)
        try:
            start_date = timezone.datetime.fromisoformat(start).date()
            end_date = timezone.datetime.fromisoformat(end).date()
        except ValueError:
            return Response({"detail": "Dates must use YYYY-MM-DD."}, status=400)
        if start_date >= end_date:
            return Response({"detail": "End date must be after start date."}, status=400)
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
        return Response(booking_payload(booking), status=status.HTTP_201_CREATED)


class MyBookingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        bookings = Booking.objects.filter(borrower=request.user).select_related(
            "equipment_unit__equipment_type", "borrower"
        ).order_by("-start_date", "-id")
        return Response([booking_payload(b) for b in bookings])


class CancelBookingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk, borrower=request.user)
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=404)
        if booking.status != Booking.Status.RESERVED:
            return Response({"detail": "Only reserved bookings can be cancelled."}, status=400)
        if booking.start_date <= timezone.localdate():
            return Response({"detail": "A booking can only be cancelled before its start date."}, status=400)
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        return Response(booking_payload(booking))


class StaffBookingActionAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk, action):
        try:
            booking = Booking.objects.select_related("equipment_unit__equipment_type", "borrower").get(pk=pk)
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=404)
        try:
            if action == "checkout":
                checkout_booking(booking)
                return Response(booking_payload(booking))
            if action == "return":
                return_booking(booking)
                return Response({
                    "booking": booking_payload(booking),
                    "late_fee": str(booking.late_fee_charged),
                    "refund_amount": str(booking.refund_amount),
                })
        except ValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)
        return Response({"detail": "Unknown action."}, status=404)


class TransferAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        try:
            booking = Booking.objects.select_related("borrower", "equipment_unit__equipment_type").get(pk=pk)
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found."}, status=404)
        borrower_id = request.data.get("new_borrower_id")
        try:
            new_borrower = get_user_model().objects.get(pk=borrower_id, is_active=True)
        except (get_user_model().DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Select a valid new borrower."}, status=400)
        try:
            due_date = booking.due_date
            transfer_booking(booking, new_borrower, request.user)
        except ValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)
        return Response({"booking": booking_payload(booking), "due_date_unchanged": due_date.isoformat()})


class DashboardAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        today = timezone.localdate()
        bookings = list(
            Booking.objects.filter(
                status__in=[Booking.Status.RESERVED, Booking.Status.CHECKED_OUT],
                due_date__lte=today + timedelta(days=2),
            ).select_related("borrower", "equipment_unit__equipment_type").order_by("due_date", "id")
        )
        return Response([
            {**booking_payload(booking), "days_overdue": max(0, (today - booking.due_date).days)}
            for booking in bookings
        ])


def user_payload(user):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.get_full_name() or user.username,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


def booking_payload(booking):
    return {
        "id": booking.id,
        "borrower": user_payload(booking.borrower),
        "equipment_unit": {
            "id": booking.equipment_unit_id,
            "asset_tag": booking.equipment_unit.asset_tag,
            "status": booking.equipment_unit.status,
            "name": booking.equipment_unit.equipment_type.name,
            "category": booking.equipment_unit.equipment_type.category,
            "deposit_amount": str(booking.equipment_unit.equipment_type.deposit_amount),
            "daily_late_fee": str(booking.equipment_unit.equipment_type.daily_late_fee),
        },
        "start_date": booking.start_date.isoformat(),
        "due_date": booking.due_date.isoformat(),
        "returned_date": booking.returned_date.isoformat() if booking.returned_date else None,
        "deposit_charged": str(booking.deposit_charged),
        "late_fee_charged": str(booking.late_fee_charged),
        "refund_amount": str(booking.refund_amount),
        "status": booking.status,
    }
