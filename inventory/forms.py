from django import forms

from .models import Booking, EquipmentType


class AvailabilityForm(forms.Form):
    category = forms.ChoiceField(
        choices=[("", "All categories")] + list(EquipmentType.Category.choices)
    )
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and start >= end:
            raise forms.ValidationError("End date must be after start date.")
        return cleaned


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["equipment_unit", "start_date", "due_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        due = cleaned.get("due_date")
        if start and due and start >= due:
            raise forms.ValidationError("Due date must be after start date.")
        return cleaned
