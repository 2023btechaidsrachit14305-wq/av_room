from django.urls import path

from .api import AvailabilityAPIView, BookingCreateAPIView, DashboardAPIView, StaffBookingActionAPIView, TransferAPIView
from .borrower_api import BorrowerListAPIView

urlpatterns = [
    path("availability/", AvailabilityAPIView.as_view(), name="api_availability"),
    path("bookings/", BookingCreateAPIView.as_view(), name="api_bookings"),
    path("bookings/<int:pk>/checkout/", StaffBookingActionAPIView.as_view(), {"action": "checkout"}, name="api_checkout"),
    path("bookings/<int:pk>/return/", StaffBookingActionAPIView.as_view(), {"action": "return"}, name="api_return"),
    path("bookings/<int:pk>/transfer/", TransferAPIView.as_view(), name="api_transfer"),
    path("dashboard/", DashboardAPIView.as_view(), name="api_dashboard"),
    path("borrowers/", BorrowerListAPIView.as_view(), name="api_borrowers"),
]
