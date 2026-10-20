"""
rewards/models.py  (REPLACE the starter file)

Five tables:
    RewardAccount      - one per user: current balance + lifetime points
    Reward             - the catalog
    ReturnVerification - a staff-confirmed return (the ONLY trigger for points)
    Redemption         - a request to spend points on a reward
    PointTransaction   - the ledger: one row for every change to a balance

Rules that must never be broken are ALSO written as database constraints,
so even a bug in our code cannot create a duplicate award or a negative balance.
Points are only ever changed by rewards/services.py - never write them elsewhere.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from . import config


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------
class RewardAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reward_account"
    )
    points_balance = models.PositiveIntegerField(default=0, help_text="Points that can be spent now.")
    lifetime_points = models.PositiveIntegerField(default=0, help_text="All points ever earned. Decides rank.")
    nickname = models.CharField(
        max_length=config.NICKNAME_MAX_LENGTH, blank=True,
        help_text="Optional name shown on the leaderboard. Never use your ID number.",
    )
    show_on_leaderboard = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # You can never hold more spendable points than you ever earned.
            models.CheckConstraint(
                condition=Q(points_balance__lte=F("lifetime_points")),
                name="rw_balance_not_above_lifetime",
            ),
        ]

    def __str__(self):
        return f"Rewards account #{self.pk}"

    @property
    def rank(self):
        return config.get_rank(self.lifetime_points)

    @property
    def public_name(self):
        """The ONLY name shown to other users. Never the username or ID number."""
        return self.nickname or f"Helper #{self.pk}"

    def clean(self):
        self.nickname = (self.nickname or "").strip()
        if not self.nickname:
            return
        if self.nickname.replace(" ", "").isdigit():
            raise ValidationError({"nickname": "A nickname cannot be only numbers."})
        id_number = getattr(self.user, "id_number", None) if self.user_id else None
        if id_number and id_number.lower() in self.nickname.lower():
            raise ValidationError({"nickname": "Your nickname cannot contain your ID number."})


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
class Reward(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    points_cost = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    stock = models.PositiveIntegerField(
        null=True, blank=True, help_text="Leave blank for unlimited stock."
    )
    is_active = models.BooleanField(default=True, help_text="Untick to hide it instead of deleting it.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["points_cost", "name"]
        constraints = [
            models.CheckConstraint(condition=Q(points_cost__gte=1), name="rw_reward_cost_positive"),
        ]

    def __str__(self):
        return self.name

    @property
    def is_available(self):
        return self.is_active and (self.stock is None or self.stock > 0)


# ---------------------------------------------------------------------------
# Verified returns (the only way to earn points)
# ---------------------------------------------------------------------------
class ReturnVerification(models.Model):
    class Tier(models.TextChoices):
        STANDARD = "standard", "Standard return"
        HIGH_VALUE = "high_value", "High-value return"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    finder = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="returns_made",
        help_text="The person who found the item and handed it in. Receives the points.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="returns_received",
        null=True, blank=True, help_text="The person who got the item back (if known).",
    )
    item_name = models.CharField(max_length=100)
    # A plain number, NOT a ForeignKey: LostItem may still change in the other
    # group members' work, and we do not want our migrations tied to theirs.
    lost_item_id = models.PositiveIntegerField(
        null=True, blank=True, help_text="LostItem id, if the item is in the system."
    )
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.STANDARD)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    points_awarded = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One active (pending or verified) record per lost item: no farming.
            models.UniqueConstraint(
                fields=["lost_item_id"],
                condition=Q(lost_item_id__isnull=False, status__in=["pending", "verified"]),
                name="rw_one_active_return_per_item",
                violation_error_message="This item already has an active return record.",
            ),
            models.CheckConstraint(
                condition=~Q(finder=F("owner")), name="rw_finder_not_owner",
                violation_error_message="The finder and the owner cannot be the same person.",
            ),
            # Pending = nobody reviewed it. Anything else = reviewer and time recorded.
            models.CheckConstraint(
                condition=(
                    Q(status="pending", reviewed_by__isnull=True, reviewed_at__isnull=True)
                    | (~Q(status="pending") & Q(reviewed_by__isnull=False, reviewed_at__isnull=False))
                ),
                name="rw_return_review_fields",
            ),
            # A verified return can never be verified by the finder or the owner.
            models.CheckConstraint(
                condition=~Q(status="verified") | ~Q(reviewed_by=F("finder")),
                name="rw_reviewer_not_finder",
            ),
            models.CheckConstraint(
                condition=~Q(status="verified") | ~Q(reviewed_by=F("owner")),
                name="rw_reviewer_not_owner",
            ),
            # Points are recorded only on verified returns.
            models.CheckConstraint(
                condition=(
                    Q(status="verified", points_awarded__gt=0)
                    | (~Q(status="verified") & Q(points_awarded=0))
                ),
                name="rw_points_only_if_verified",
            ),
        ]

    def __str__(self):
        return f"Return #{self.pk}: {self.item_name} ({self.get_status_display()})"

    @property
    def tier_points(self):
        return config.TIER_POINTS[self.tier]

    def clean(self):
        if self.owner_id and self.owner_id == self.finder_id:
            raise ValidationError("The finder and the owner cannot be the same person.")


# ---------------------------------------------------------------------------
# Redemptions
# ---------------------------------------------------------------------------
class Redemption(models.Model):
    """
    Lifecycle (enforced in services.py, see ALLOWED_TRANSITIONS there):

        PENDING  --approve-->  APPROVED  --fulfill-->  FULFILLED   (end, never refunded)
        PENDING  --reject--->  REJECTED                            (end, refunded once)
        APPROVED --reject--->  REJECTED                            (end, refunded once)
        PENDING  --cancel--->  CANCELLED  (by the owner only)      (end, refunded once)

    Points are taken (held) when the request is made, and given back only on
    REJECTED or CANCELLED.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        FULFILLED = "fulfilled", "Fulfilled"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    account = models.ForeignKey(RewardAccount, on_delete=models.PROTECT, related_name="redemptions")
    reward = models.ForeignKey(Reward, on_delete=models.PROTECT, related_name="redemptions")
    points_spent = models.PositiveIntegerField(help_text="Price at the time of the request.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    stock_reserved = models.BooleanField(
        default=False, help_text="True if one unit of stock was taken for this request."
    )
    refunded = models.BooleanField(default=False)
    # Created by the redeem form; a repeated submit with the same key does nothing.
    idempotency_key = models.UUIDField(unique=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    staff_note = models.TextField(blank=True)
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True
    )
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(points_spent__gt=0), name="rw_redemption_spent_positive"),
            # "refunded" is true exactly when the redemption was rejected or cancelled.
            models.CheckConstraint(
                condition=(
                    Q(refunded=True, status__in=["rejected", "cancelled"])
                    | Q(refunded=False, status__in=["pending", "approved", "fulfilled"])
                ),
                name="rw_refund_matches_status",
            ),
            models.CheckConstraint(
                condition=~Q(status="fulfilled") | Q(fulfilled_at__isnull=False, fulfilled_by__isnull=False),
                name="rw_fulfilled_has_staff_and_time",
            ),
        ]

    def __str__(self):
        return f"Redemption #{self.pk}"


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------
class PointTransaction(models.Model):
    """Append-only history. Rows are never edited or deleted."""

    class Kind(models.TextChoices):
        RETURN_AWARD = "return_award", "Return award"
        REDEMPTION_HOLD = "redemption_hold", "Redemption hold"
        REDEMPTION_REFUND = "redemption_refund", "Redemption refund"

    account = models.ForeignKey(RewardAccount, on_delete=models.PROTECT, related_name="transactions")
    amount = models.IntegerField(help_text="Positive = points added, negative = points taken.")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    reason = models.CharField(max_length=200)
    return_verification = models.ForeignKey(
        ReturnVerification, on_delete=models.PROTECT, null=True, blank=True, related_name="transactions"
    )
    redemption = models.ForeignKey(
        Redemption, on_delete=models.PROTECT, null=True, blank=True, related_name="transactions"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # Each kind must have the right sign and the right link.
            models.CheckConstraint(
                condition=(
                    Q(kind="return_award", amount__gt=0,
                      return_verification__isnull=False, redemption__isnull=True)
                    | Q(kind="redemption_hold", amount__lt=0,
                        redemption__isnull=False, return_verification__isnull=True)
                    | Q(kind="redemption_refund", amount__gt=0,
                        redemption__isnull=False, return_verification__isnull=True)
                ),
                name="rw_tx_valid_shape",
            ),
            # A return can award points only once.
            models.UniqueConstraint(
                fields=["return_verification"], condition=Q(kind="return_award"),
                name="rw_one_award_per_return",
            ),
            # A redemption has at most one hold and at most one refund.
            models.UniqueConstraint(
                fields=["redemption", "kind"], condition=Q(redemption__isnull=False),
                name="rw_one_tx_kind_per_redemption",
            ),
        ]

    def __str__(self):
        return f"{self.amount:+d} ({self.get_kind_display()})"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Ledger rows can never be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Ledger rows can never be deleted.")