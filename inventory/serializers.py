from rest_framework import serializers

from .models import Booking, EquipmentType, EquipmentUnit


class EquipmentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentType
        fields = ["id", "name", "category", "deposit_amount", "daily_late_fee"]


class EquipmentUnitSerializer(serializers.ModelSerializer):
    equipment_type = EquipmentTypeSerializer(read_only=True)

    class Meta:
        model = EquipmentUnit
        fields = ["id", "asset_tag", "status", "equipment_type"]


class BookingSerializer(serializers.ModelSerializer):
    equipment_unit = serializers.PrimaryKeyRelatedField(queryset=EquipmentUnit.objects.select_related("equipment_type"))
    borrower_id = serializers.IntegerField(source="borrower.id", read_only=True)
    refund_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "borrower_id", "equipment_unit", "start_date", "due_date",
            "returned_date", "deposit_charged", "late_fee_charged", "refund_amount", "status",
        ]
        read_only_fields = ["returned_date", "deposit_charged", "late_fee_charged", "status"]
