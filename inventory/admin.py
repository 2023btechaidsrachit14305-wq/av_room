from django.contrib import admin

from .models import Booking, EquipmentType, EquipmentUnit


@admin.register(EquipmentType)
class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "deposit_amount", "daily_late_fee")


@admin.register(EquipmentUnit)
class EquipmentUnitAdmin(admin.ModelAdmin):
    list_display = ("asset_tag", "equipment_type", "status")


@admin.action(description="Check out selected bookings")
def checkout_bookings(modeladmin, request, queryset):
    for booking in queryset.filter(status=Booking.Status.RESERVED):
        booking.status = Booking.Status.CHECKED_OUT
        booking.equipment_unit.status = EquipmentUnit.Status.CHECKED_OUT
        booking.equipment_unit.save(update_fields=["status"])
        booking.save(update_fields=["status"])


@admin.action(description="Mark selected bookings returned")
def return_bookings(modeladmin, request, queryset):
    from django.utils import timezone
    for booking in queryset.filter(status=Booking.Status.CHECKED_OUT):
        returned_date = timezone.localdate()
        late_days = max(0, (returned_date - booking.due_date).days)
        late_fee = min(
            booking.deposit_charged,
            late_days * booking.equipment_unit.equipment_type.daily_late_fee,
        )
        booking.returned_date = returned_date
        booking.late_fee_charged = late_fee
        booking.status = Booking.Status.RETURNED
        booking.equipment_unit.status = EquipmentUnit.Status.AVAILABLE
        booking.equipment_unit.save(update_fields=["status"])
        booking.save(update_fields=["returned_date", "late_fee_charged", "status"])


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "borrower", "equipment_unit", "start_date", "due_date",
        "returned_date", "deposit_charged", "late_fee_charged",
        "refund_amount", "status",
    )
    list_filter = ("status", "equipment_unit__equipment_type__category")
    search_fields = ("borrower__username", "equipment_unit__asset_tag")
    actions = (checkout_bookings, return_bookings)

    @admin.display(description="Refund amount")
    def refund_amount(self, obj):
        return obj.deposit_charged - obj.late_fee_charged
