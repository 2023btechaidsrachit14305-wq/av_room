from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse

from .models import Booking, EquipmentType, EquipmentUnit, TransferLog
from .services import checkout_booking, return_booking, transfer_booking


@admin.register(EquipmentType)
class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "deposit_amount", "daily_late_fee")


@admin.register(EquipmentUnit)
class EquipmentUnitAdmin(admin.ModelAdmin):
    list_display = ("asset_tag", "equipment_type", "status")


@admin.action(description="Check out selected bookings")
def checkout_bookings(modeladmin, request, queryset):
    changed = 0
    for booking in queryset:
        try:
            checkout_booking(booking)
            changed += 1
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    if changed:
        messages.success(request, f"Checked out {changed} booking(s).")


@admin.action(description="Mark selected bookings returned")
def return_bookings(modeladmin, request, queryset):
    changed = 0
    for booking in queryset:
        try:
            return_booking(booking)
            changed += 1
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    if changed:
        messages.success(request, f"Returned {changed} booking(s).")


@admin.action(description="Transfer to another borrower")
def transfer_selected_bookings(modeladmin, request, queryset):
    ids = ",".join(str(pk) for pk in queryset.values_list("pk", flat=True))
    return redirect(reverse("admin:inventory_booking_transfer") + f"?ids={ids}")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "borrower", "equipment_unit", "start_date", "due_date", "returned_date",
        "deposit_charged", "late_fee_charged", "refund_amount", "status",
    )
    list_filter = ("status", "equipment_unit__equipment_type__category")
    search_fields = ("borrower__username", "equipment_unit__asset_tag")
    actions = (checkout_bookings, return_bookings, transfer_selected_bookings)

    @admin.display(description="Refund amount")
    def refund_amount(self, obj):
        return obj.refund_amount

    def get_urls(self):
        urls = super().get_urls()
        custom = [path("transfer/", self.admin_site.admin_view(self.transfer_view), name="inventory_booking_transfer")]
        return custom + urls

    def transfer_view(self, request):
        raw_ids = request.GET.get("ids", "") or request.POST.get("ids", "")
        ids = [int(value) for value in raw_ids.split(",") if value.isdigit()]
        bookings = list(Booking.objects.filter(pk__in=ids).select_related("borrower", "equipment_unit"))
        if not bookings:
            messages.error(request, "Select at least one booking to transfer.")
            return redirect("admin:inventory_booking_changelist")

        if request.method == "POST":
            borrower_id = request.POST.get("new_borrower")
            from django.contrib.auth import get_user_model
            borrower = get_object_or_404(get_user_model(), pk=borrower_id)
            transferred = 0
            for booking in bookings:
                try:
                    transfer_booking(booking, borrower, request.user)
                    transferred += 1
                except ValidationError as exc:
                    messages.error(request, f"Booking #{booking.pk}: {exc.messages[0]}")
            if transferred:
                messages.success(request, f"Transferred {transferred} booking(s) to {borrower}.")
            return redirect("admin:inventory_booking_changelist")

        from django.contrib.auth import get_user_model
        borrowers = get_user_model().objects.filter(is_active=True).order_by("username")
        return render(request, "admin/inventory/booking/transfer.html", {
            "title": "Transfer bookings",
            "bookings": bookings,
            "borrowers": borrowers,
            "ids": raw_ids,
            "opts": self.model._meta,
        })


@admin.register(TransferLog)
class TransferLogAdmin(admin.ModelAdmin):
    list_display = ("booking", "from_user", "to_user", "transferred_at", "transferred_by")
    list_filter = ("transferred_at",)
    search_fields = ("booking__id", "from_user__username", "to_user__username", "transferred_by__username")
    readonly_fields = ("transferred_at",)
