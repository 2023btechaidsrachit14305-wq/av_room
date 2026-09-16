from django.contrib import admin

from .models import Booking, EquipmentType, EquipmentUnit


@admin.register(EquipmentType)
class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "deposit_amount", "daily_late_fee")


@admin.register(EquipmentUnit)
class EquipmentUnitAdmin(admin.ModelAdmin):
    list_display = ("asset_tag", "equipment_type", "status")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "borrower",
        "equipment_unit",
        "start_date",
        "due_date",
        "returned_date",
        "deposit_charged",
        "late_fee_charged",
        "status",
    )
