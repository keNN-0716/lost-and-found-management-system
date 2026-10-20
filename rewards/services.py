"""
rewards/services.py  (NEW FILE)

ALL changes to points, stock and statuses happen here. Views, admin actions and
your groupmates' code must call these functions and never edit balances directly.

How the safety works (simple version):
  * Every function that changes money-like data runs inside transaction.atomic(),
    so the balance change and its ledger row succeed together or not at all.
  * select_for_update() locks the rows we are changing, so two requests at the
    same moment take turns instead of both succeeding.
  * Lock order is always: redemption -> account -> reward (prevents deadlocks).
  * Database constraints in models.py are the last safety net.

For your groupmates, the one function they need is record_verified_return().
"""
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone

from . import config
from .models import (
    PointTransaction, Redemption, Reward, RewardAccount, ReturnVerification,
)

Status = ReturnVerification.Status
RStatus = Redemption.Status
Kind = PointTransaction.Kind


# ---------------------------------------------------------------------------
# Errors. The message of each one is safe to show to the user.
# ---------------------------------------------------------------------------
class RewardsError(Exception):
    """Base class for expected, user-facing problems."""


class RuleViolation(RewardsError):
    pass


class InvalidTransition(RewardsError):
    pass


class RewardUnavailable(RewardsError):
    pass


class OutOfStock(RewardsError):
    pass


class InsufficientPoints(RewardsError):
    pass


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------
def is_rewards_staff(user):
    """
    Active superuser, OR active user with is_staff=True AND role == 'Management'.
    Used by the services below AND by the admin pages.
    """
    if user is None or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return bool(user.is_staff) and getattr(user, "role", None) == config.MANAGEMENT_ROLE


def require_rewards_staff(user):
    if not is_rewards_staff(user):
        raise PermissionDenied("Only active Management staff can do this.")


# ---------------------------------------------------------------------------
# Internal helpers (must be called inside transaction.atomic())
# ---------------------------------------------------------------------------
def _get_locked_account(user):
    """Get (or create) the user's account and lock its row until the transaction ends."""
    RewardAccount.objects.get_or_create(user=user)
    return RewardAccount.objects.select_for_update().get(user=user)


def _apply_ledger(account, amount, kind, reason, *, return_verification=None,
                  redemption=None, earned=False):
    """
    The ONLY place a balance changes. The balance update and the ledger row are
    written together. `earned=True` also raises lifetime points (used for awards).
    """
    account.points_balance += amount
    if earned:
        account.lifetime_points += amount
    account.save(update_fields=["points_balance", "lifetime_points"])
    return PointTransaction.objects.create(
        account=account, amount=amount, kind=kind, reason=reason,
        return_verification=return_verification, redemption=redemption,
    )


# ---------------------------------------------------------------------------
# Verified returns
# ---------------------------------------------------------------------------
def validate_new_return(*, finder, owner, lost_item_id):
    """Shared checks used by the services and by the admin add form."""
    if not finder.is_active:
        raise RuleViolation("The finder's account is not active.")
    if owner is not None and owner.pk == finder.pk:
        raise RuleViolation("The finder and the owner cannot be the same person.")
    if lost_item_id is not None and ReturnVerification.objects.filter(
        lost_item_id=lost_item_id, status__in=[Status.PENDING, Status.VERIFIED]
    ).exists():
        raise RuleViolation("This item already has an active return record.")


def create_return_verification(*, finder, owner, item_name, tier, created_by,
                               lost_item_id=None, notes=""):
    """Staff records a return. Status is PENDING: no points are given yet."""
    require_rewards_staff(created_by)
    if tier not in config.TIER_POINTS:
        raise RuleViolation("Unknown return tier.")
    validate_new_return(finder=finder, owner=owner, lost_item_id=lost_item_id)
    try:
        with transaction.atomic():
            return ReturnVerification.objects.create(
                finder=finder, owner=owner, item_name=item_name, tier=tier,
                lost_item_id=lost_item_id, notes=notes, created_by=created_by,
            )
    except IntegrityError:
        # Two staff saving the same item at the same moment.
        raise RuleViolation("This item already has an active return record.")


def verify_return(verification, verified_by):
    """
    PENDING -> VERIFIED and award the points to the finder, exactly once.
    """
    require_rewards_staff(verified_by)
    with transaction.atomic():
        v = ReturnVerification.objects.select_for_update().get(pk=verification.pk)
        if v.status != Status.PENDING:
            raise InvalidTransition(f"This return is already {v.get_status_display().lower()}.")
        if verified_by.pk in (v.finder_id, v.owner_id):
            raise RuleViolation("You cannot verify a return that you are personally involved in.")
        if not v.finder.is_active:
            raise RuleViolation("The finder's account is not active.")

        points = config.TIER_POINTS[v.tier]
        account = _get_locked_account(v.finder)

        v.status = Status.VERIFIED
        v.reviewed_by = verified_by
        v.reviewed_at = timezone.now()
        v.points_awarded = points
        v.save(update_fields=["status", "reviewed_by", "reviewed_at", "points_awarded"])

        _apply_ledger(account, points, Kind.RETURN_AWARD, f"Verified return: {v.item_name}",
                      return_verification=v, earned=True)
    return v


def reject_return(verification, rejected_by, notes=""):
    """PENDING -> REJECTED. No points."""
    require_rewards_staff(rejected_by)
    with transaction.atomic():
        v = ReturnVerification.objects.select_for_update().get(pk=verification.pk)
        if v.status != Status.PENDING:
            raise InvalidTransition(f"This return is already {v.get_status_display().lower()}.")
        v.status = Status.REJECTED
        v.reviewed_by = rejected_by
        v.reviewed_at = timezone.now()
        if notes:
            v.notes = f"{v.notes}\n{notes}".strip()
        v.save(update_fields=["status", "reviewed_by", "reviewed_at", "notes"])
    return v


def record_verified_return(*, finder, owner, item_name, tier, verified_by,
                           lost_item_id=None, notes=""):
    """
    THE FUNCTION FOR GROUPMATES: call this when your claim/return flow confirms a handover.
    Creates the record and awards the points in ONE transaction. If anything fails, nothing is saved.
    The same lost_item_id can only be rewarded once.
    """
    require_rewards_staff(verified_by)
    with transaction.atomic():
        v = create_return_verification(
            finder=finder, owner=owner, item_name=item_name, tier=tier,
            created_by=verified_by, lost_item_id=lost_item_id, notes=notes,
        )
        return verify_return(v, verified_by)


# ---------------------------------------------------------------------------
# Redemptions
# ---------------------------------------------------------------------------
# The complete list of allowed moves. Anything not listed here is refused.
#   action   : {current status: new status}
ALLOWED_TRANSITIONS = {
    "approve": {RStatus.PENDING: RStatus.APPROVED},
    "fulfill": {RStatus.APPROVED: RStatus.FULFILLED},
    "reject": {RStatus.PENDING: RStatus.REJECTED, RStatus.APPROVED: RStatus.REJECTED},
    "cancel": {RStatus.PENDING: RStatus.CANCELLED},   # approved items can only be rejected by staff
}


def _lock_redemption(redemption):
    return Redemption.objects.select_for_update().get(pk=redemption.pk)


_ACTION_WORDS = {"approve": "approved", "fulfill": "fulfilled",
                 "reject": "rejected", "cancel": "cancelled"}


def _next_status(r, action):
    """Return the new status, or raise InvalidTransition if the move is not allowed."""
    try:
        return ALLOWED_TRANSITIONS[action][r.status]
    except KeyError:
        raise InvalidTransition(
            f"A {r.get_status_display().lower()} redemption cannot be {_ACTION_WORDS[action]}."
        )


def _refuse_own_review(r, reviewer):
    if r.account.user_id == reviewer.pk:
        raise RuleViolation("You cannot review your own redemption.")


def request_redemption(*, user, reward_id, idempotency_key):
    """
    Take the points and one unit of stock right now ("hold"), and create a PENDING request.
    Returns (redemption, created). If the same idempotency_key is sent again
    (double click, refresh), the existing redemption is returned with created=False.
    """
    if not user.is_active:
        raise PermissionDenied("Your account is not active.")

    with transaction.atomic():
        account = _get_locked_account(user)   # one request per user at a time

        existing = Redemption.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.account_id != account.pk:
                raise RuleViolation("This request is not valid.")
            return existing, False

        try:
            reward = Reward.objects.select_for_update().get(pk=reward_id)
        except Reward.DoesNotExist:
            raise RewardUnavailable("This reward does not exist.")
        if not reward.is_active:
            raise RewardUnavailable("This reward is no longer available.")
        if reward.stock is not None and reward.stock <= 0:
            raise OutOfStock("This reward is out of stock.")
        if account.points_balance < reward.points_cost:
            raise InsufficientPoints(
                f"You need {reward.points_cost} points but have {account.points_balance}."
            )

        redemption = Redemption.objects.create(
            account=account, reward=reward, points_spent=reward.points_cost,
            stock_reserved=reward.stock is not None, idempotency_key=idempotency_key,
        )
        if reward.stock is not None:
            reward.stock -= 1
            reward.save(update_fields=["stock"])
        _apply_ledger(account, -reward.points_cost, Kind.REDEMPTION_HOLD,
                      f"Redeemed: {reward.name}", redemption=redemption)
    return redemption, True


def approve_redemption(redemption, reviewer):
    """PENDING -> APPROVED. Points stay held."""
    require_rewards_staff(reviewer)
    with transaction.atomic():
        r = _lock_redemption(redemption)
        _refuse_own_review(r, reviewer)
        r.status = _next_status(r, "approve")
        r.reviewed_by = reviewer
        r.reviewed_at = timezone.now()
        r.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    return r


def fulfill_redemption(redemption, reviewer):
    """APPROVED -> FULFILLED (the student received the reward). Never refunds."""
    require_rewards_staff(reviewer)
    with transaction.atomic():
        r = _lock_redemption(redemption)
        _refuse_own_review(r, reviewer)
        r.status = _next_status(r, "fulfill")
        r.fulfilled_by = reviewer
        r.fulfilled_at = timezone.now()
        r.save(update_fields=["status", "fulfilled_by", "fulfilled_at", "updated_at"])
    return r


def _refund(r, new_status):
    """
    Give the points (and the stock unit, if one was taken) back - exactly once.
    Caller already holds the lock on `r` and has checked the transition.
    Three layers stop a second refund: the status check, the `refunded` flag,
    and the unique constraint on the ledger.
    """
    if r.refunded:
        raise InvalidTransition("This redemption was already refunded.")
    account = _get_locked_account(r.account.user)
    reward = Reward.objects.select_for_update().get(pk=r.reward_id)

    if r.stock_reserved and reward.stock is not None:
        reward.stock += 1
        reward.save(update_fields=["stock"])
    _apply_ledger(account, r.points_spent, Kind.REDEMPTION_REFUND,
                  f"Refund: {reward.name}", redemption=r)   # lifetime points unchanged

    r.status = new_status
    r.refunded = True


def reject_redemption(redemption, reviewer, note=""):
    """PENDING or APPROVED -> REJECTED, with a refund."""
    require_rewards_staff(reviewer)
    with transaction.atomic():
        r = _lock_redemption(redemption)
        _refuse_own_review(r, reviewer)
        new_status = _next_status(r, "reject")
        _refund(r, new_status)
        r.reviewed_by = reviewer
        r.reviewed_at = timezone.now()
        r.staff_note = note
        r.save(update_fields=["status", "refunded", "reviewed_by", "reviewed_at",
                              "staff_note", "updated_at"])
    return r


def cancel_redemption(redemption, user):
    """PENDING -> CANCELLED by the student who made it, with a refund."""
    with transaction.atomic():
        r = _lock_redemption(redemption)
        if r.account.user_id != user.pk:
            raise PermissionDenied("You can only cancel your own redemptions.")
        new_status = _next_status(r, "cancel")
        _refund(r, new_status)
        r.save(update_fields=["status", "refunded", "updated_at"])
    return r


# ---------------------------------------------------------------------------
# Leaderboard (privacy-safe: only public names and points are ever returned)
# ---------------------------------------------------------------------------
def _eligible_accounts():
    return RewardAccount.objects.filter(show_on_leaderboard=True, user__is_active=True)


def _public_name(nickname, account_id):
    return nickname or f"Helper #{account_id}"


def get_leaderboard(period="all", user=None, limit=config.LEADERBOARD_SIZE):
    """
    period: "all"   -> ranked by lifetime points
            "month" -> ranked by points earned this calendar month
    Equal points share the same rank number; order inside a tie is by account id.
    Returns {"entries": [...], "me": entry-or-None}. Entry keys:
    rank, name, rank_title, points, is_me. Never contains usernames or ID numbers.
    """
    if period not in ("all", "month"):
        raise ValueError("period must be 'all' or 'month'")

    me_account = None
    if user is not None and getattr(user, "is_authenticated", False):
        me_account = _eligible_accounts().filter(user=user).first()

    if period == "all":
        rows = (_eligible_accounts().filter(lifetime_points__gt=0)
                .annotate(points=F("lifetime_points"))
                .order_by("-lifetime_points", "id")
                .values_list("id", "nickname", "lifetime_points", "points")[:limit])
        my_points = me_account.lifetime_points if me_account else 0
        count_higher = lambda: _eligible_accounts().filter(lifetime_points__gt=my_points).count()
    else:
        start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        awards = PointTransaction.objects.filter(
            kind=Kind.RETURN_AWARD, created_at__gte=start,
            account__show_on_leaderboard=True, account__user__is_active=True,
        )
        rows = (awards.values("account_id", "account__nickname", "account__lifetime_points")
                .annotate(points=Sum("amount")).order_by("-points", "account_id")
                .values_list("account_id", "account__nickname", "account__lifetime_points", "points")[:limit])
        my_points = 0
        if me_account:
            my_points = awards.filter(account=me_account).aggregate(total=Sum("amount"))["total"] or 0
        count_higher = lambda: (awards.values("account_id").annotate(points=Sum("amount"))
                                .filter(points__gt=my_points).count())

    entries, previous_points, previous_rank = [], None, 0
    for position, (account_id, nickname, lifetime, points) in enumerate(rows, start=1):
        rank = previous_rank if points == previous_points else position
        entries.append({
            "rank": rank,
            "name": _public_name(nickname, account_id),
            "rank_title": config.get_rank(lifetime),
            "points": points,
            "is_me": me_account is not None and account_id == me_account.pk,
        })
        previous_points, previous_rank = points, rank

    me = next((e for e in entries if e["is_me"]), None)
    if me is None and me_account is not None and my_points > 0:
        me = {
            "rank": count_higher() + 1, "name": me_account.public_name,
            "rank_title": me_account.rank, "points": my_points, "is_me": True,
        }
    return {"entries": entries, "me": me}