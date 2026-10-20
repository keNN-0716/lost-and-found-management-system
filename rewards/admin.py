"""
rewards/admin.py  (REPLACE the starter file)

Only "rewards staff" (see services.is_rewards_staff) can see or use these pages:
an active superuser, or an active user with is_staff=True AND role == 'Management'.

Records that carry points (accounts, ledger, statuses) are READ-ONLY here.
Staff change them only through the action buttons, which call rewards/services.py,
so refunds, awards and duplicate checks can never be skipped.
"""
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError

from . import services
from .models import (
    PointTransaction, Redemption, Reward, RewardAccount, ReturnVerification,
)


class RewardsStaffMixin:
    """Gives access only to rewards staff. Child classes opt in to add/change/delete."""

    allow_add = False
    allow_change = False
    allow_delete = False

    def has_module_permission(self, request):
        return services.is_rewards_staff(request.user)

    def has_view_permission(self, request, obj=None):
        return services.is_rewards_staff(request.user)

    def has_add_permission(self, request):
        return self.allow_add and services.is_rewards_staff(request.user)

    def has_change_permission(self, request, obj=None):
        return self.allow_change and services.is_rewards_staff(request.user)

    def has_delete_permission(self, request, obj=None):
        return self.allow_delete and services.is_rewards_staff(request.user)


def run_action(request, queryset, service_function, done_word, *extra):
    """Run one service function per selected row and report successes and errors."""
    done = 0
    for obj in queryset:
        try:
            service_function(obj, request.user, *extra)
            done += 1
        except (services.RewardsError, PermissionDenied) as exc:
            messages.error(request, f"{obj}: {exc or 'Not allowed.'}")
    if done:
        messages.success(request, f"{done} record(s) {done_word}.")


# ---------------------------------------------------------------------------
@admin.register(Reward)
class RewardAdmin(RewardsStaffMixin, admin.ModelAdmin):
    allow_add = True
    allow_change = True          # no delete: untick "is active" to hide a reward
    list_display = ("name", "points_cost", "stock", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


# ---------------------------------------------------------------------------
class ReturnVerificationAddForm(forms.ModelForm):
    class Meta:
        model = ReturnVerification
        fields = ("finder", "owner", "item_name", "lost_item_id", "tier", "notes")

    def clean(self):
        cleaned = super().clean()
        finder = cleaned.get("finder")
        if finder is not None:
            try:
                services.validate_new_return(
                    finder=finder, owner=cleaned.get("owner"), lost_item_id=cleaned.get("lost_item_id"),
                )
            except services.RewardsError as exc:
                raise ValidationError(str(exc))
        return cleaned


@admin.register(ReturnVerification)
class ReturnVerificationAdmin(RewardsStaffMixin, admin.ModelAdmin):
    allow_add = True             # staff can record a return; saved as PENDING (no points yet)
    form = ReturnVerificationAddForm
    list_display = ("item_name", "finder", "owner", "tier", "status", "points_awarded", "created_at")
    list_filter = ("status", "tier")
    list_select_related = ("finder", "owner")
    search_fields = ("item_name",)
    actions = ["verify_returns", "reject_returns"]

    def get_fields(self, request, obj=None):
        if obj is None:  # the "add" page: only what staff may fill in
            return ("finder", "owner", "item_name", "lost_item_id", "tier", "notes")
        return ("item_name", "finder", "owner", "lost_item_id", "tier", "status", "points_awarded",
                "notes", "created_by", "created_at", "reviewed_by", "reviewed_at")  # read-only page

    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        obj.status = ReturnVerification.Status.PENDING
        super().save_model(request, obj, form, change)

    @admin.action(description="Verify selected returns and award points")
    def verify_returns(self, request, queryset):
        run_action(request, queryset, services.verify_return, "verified")

    @admin.action(description="Reject selected returns (no points)")
    def reject_returns(self, request, queryset):
        run_action(request, queryset, services.reject_return, "rejected")


# ---------------------------------------------------------------------------
@admin.register(Redemption)
class RedemptionAdmin(RewardsStaffMixin, admin.ModelAdmin):
    list_display = ("id", "account", "reward", "points_spent", "status", "created_at")
    list_filter = ("status", "reward")
    list_select_related = ("account__user", "reward")
    actions = ["approve_redemptions", "fulfill_redemptions", "reject_redemptions"]

    @admin.action(description="Approve selected (pending -> approved)")
    def approve_redemptions(self, request, queryset):
        run_action(request, queryset, services.approve_redemption, "approved")

    @admin.action(description="Mark selected as fulfilled (reward handed over)")
    def fulfill_redemptions(self, request, queryset):
        run_action(request, queryset, services.fulfill_redemption, "fulfilled")

    @admin.action(description="Reject selected and refund points")
    def reject_redemptions(self, request, queryset):
        run_action(request, queryset, services.reject_redemption, "rejected and refunded")


# ---------------------------------------------------------------------------
@admin.register(RewardAccount)
class RewardAccountAdmin(RewardsStaffMixin, admin.ModelAdmin):
    list_display = ("user", "points_balance", "lifetime_points", "show_on_leaderboard")
    list_select_related = ("user",)
    search_fields = ("user__username", "user__id_number")


@admin.register(PointTransaction)
class PointTransactionAdmin(RewardsStaffMixin, admin.ModelAdmin):
    list_display = ("created_at", "account", "kind", "amount", "reason")
    list_filter = ("kind",)
    list_select_related = ("account",)
    date_hierarchy = "created_at"