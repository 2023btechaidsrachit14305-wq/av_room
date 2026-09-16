from django.urls import path

from .api import (
    AvailabilityAPIView,
    BookingCreateAPIView,
    CancelBookingAPIView,
    DashboardAPIView,
    MyBookingsAPIView,
    StaffBookingActionAPIView,
    TransferAPIView,
    auth_login,
    auth_logout,
    auth_me,
    auth_register,
)
from .borrower_api import BorrowerListAPIView

urlpatterns = [
    path("auth/me/", auth_me, name="api_auth_me"),
    path("auth/login/", auth_login, name="api_auth_login"),
    path("auth/register/", auth_register, name="api_auth_register"),
    path("auth/logout/", auth_logout, name="api_auth_logout"),
    path("availability/", AvailabilityAPIView.as_view(), name="api_availability"),
    path("bookings/", BookingCreateAPIView.as_view(), name="api_bookings"),
    path("my-bookings/", MyBookingsAPIView.as_view(), name="api_my_bookings"),
    path("bookings/<int:pk>/cancel/", CancelBookingAPIView.as_view(), name="api_cancel_booking"),
    path("bookings/<int:pk>/checkout/", StaffBookingActionAPIView.as_view(), {"action": "checkout"}, name="api_checkout"),
    path("bookings/<int:pk>/return/", StaffBookingActionAPIView.as_view(), {"action": "return"}, name="api_return"),
    path("bookings/<int:pk>/transfer/", TransferAPIView.as_view(), name="api_transfer"),
    path("dashboard/", DashboardAPIView.as_view(), name="api_dashboard"),
    path("borrowers/", BorrowerListAPIView.as_view(), name="api_borrowers"),
]
