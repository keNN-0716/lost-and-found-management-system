"""
rewards/forms.py

Forms for student rewards pages and Management staff queues.
"""
from django import forms
from django.contrib.auth import get_user_model

from . import config
from .models import ReturnVerification, RewardAccount

User = get_user_model()


class NicknameForm(forms.ModelForm):
    """Let the user change the name shown on the leaderboard."""

    class Meta:
        model = RewardAccount
        fields = ("nickname", "show_on_leaderboard")
        widgets = {
            "nickname": forms.TextInput(attrs={
                "class": "rw-input",
                "placeholder": "e.g. CampusHero99",
                "maxlength": config.NICKNAME_MAX_LENGTH,
                "autocomplete": "nickname",
            }),
            "show_on_leaderboard": forms.CheckboxInput(attrs={
                "class": "rw-checkbox",
            }),
        }
        labels = {
            "nickname": "Display name",
            "show_on_leaderboard": "Show me on the leaderboard",
        }
        help_texts = {
            "nickname": "This is the only name other students will see. Leave blank to use a default.",
        }


class RedeemForm(forms.Form):
    """Hidden idempotency key stops double-submit from creating two redemptions."""

    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)


class StaffNoteForm(forms.Form):
    note = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            "class": "rw-input rw-textarea",
            "rows": 3,
            "placeholder": "Optional note for the student",
        }),
        label="Staff note",
    )


class ReturnVerificationCreateForm(forms.ModelForm):
    """Management records a pending return. Points are awarded only after verify."""

    finder = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("username"),
        widget=forms.Select(attrs={"class": "rw-input"}),
        help_text="Student who found and returned the item (receives points when verified).",
    )
    owner = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("username"),
        required=False,
        widget=forms.Select(attrs={"class": "rw-input"}),
        help_text="Optional: student who got the item back.",
    )

    class Meta:
        model = ReturnVerification
        fields = ("finder", "owner", "item_name", "lost_item_id", "tier", "notes")
        widgets = {
            "item_name": forms.TextInput(attrs={
                "class": "rw-input",
                "placeholder": "e.g. Black umbrella",
            }),
            "lost_item_id": forms.NumberInput(attrs={
                "class": "rw-input",
                "placeholder": "Optional LostItem ID",
                "min": 1,
            }),
            "tier": forms.Select(attrs={"class": "rw-input"}),
            "notes": forms.Textarea(attrs={
                "class": "rw-input rw-textarea",
                "rows": 3,
                "placeholder": "Optional staff notes",
            }),
        }
        labels = {
            "item_name": "Item name",
            "lost_item_id": "Lost item ID (optional)",
            "tier": "Return tier",
            "notes": "Notes",
        }
        help_texts = {
            "tier": "Standard = 50 points. High-value = 100 points (ID, phone, wallet, etc.).",
            "lost_item_id": "If the item exists in Lost Items, enter its ID to prevent duplicate awards.",
        }
