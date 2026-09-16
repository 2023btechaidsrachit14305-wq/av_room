from django.contrib.auth.models import User
from django.db import models


class EquipmentType(models.Model):
    class Category(models.TextChoices):
        DSLR = "DSLR", "DSLR"
        PROJECTOR = "Projector", "Projector"
        MIC = "Mic", "Mic"
        TRIPOD = "Tripod", "Tripod"

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=Category.choices)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    daily_late_fee = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.category})"


class EquipmentUnit(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        BOOKED = "booked", "Booked"
        CHECKED_OUT = "checked_out", "Checked Out"
        MAINTENANCE = "maintenance", "Maintenance"

    equipment_type = models.ForeignKey(
        EquipmentType,
        on_delete=models.CASCADE,
        related_name="units",
    )
    asset_tag = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )

    class Meta:
        ordering = ["asset_tag"]

    def __str__(self):
        return f"{self.asset_tag} - {self.equipment_type.name}"


class Booking(models.Model):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        CHECKED_OUT = "checked_out", "Checked Out"
        RETURNED = "returned", "Returned"
        CANCELLED = "cancelled", "Cancelled"

    borrower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    equipment_unit = models.ForeignKey(
        EquipmentUnit,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    start_date = models.DateField()
    due_date = models.DateField()
    returned_date = models.DateField(null=True, blank=True)
    deposit_charged = models.DecimalField(max_digits=10, decimal_places=2)
    late_fee_charged = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RESERVED,
    )

    class Meta:
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return f"{self.equipment_unit.asset_tag} - {self.borrower.username} ({self.start_date})"

    @property
    def refund_amount(self):
        return self.deposit_charged - self.late_fee_charged


class TransferLog(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="transfer_logs")
    from_user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="outgoing_transfers")
    to_user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="incoming_transfers")
    transferred_at = models.DateTimeField(auto_now_add=True)
    transferred_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_transfers",
    )

    class Meta:
        ordering = ["-transferred_at"]

    def __str__(self):
        return f"Booking #{self.booking_id}: {self.from_user} → {self.to_user}"
