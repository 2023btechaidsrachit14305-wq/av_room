from django.urls import path

from . import views

urlpatterns = [
    path("availability/", views.availability, name="availability"),
    path("bookings/new/", views.create_booking_view, name="create_booking"),
    path("bookings/<int:pk>/confirmation/", views.booking_confirmation, name="booking_confirmation"),
    path("dashboard/", views.dashboard, name="dashboard"),
]
