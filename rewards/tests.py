"""
rewards/tests.py

Run with:   python manage.py test rewards
"""
import itertools
import json
import threading
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import F, Sum
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from . import config, services
from .models import PointTransaction, Redemption, Reward, RewardAccount, ReturnVerification

User = get_user_model()
_counter = itertools.count(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_user(username, *, role="Normal_User", is_staff=False, is_superuser=False, is_active=True):
    # No password on purpose: hashing passwords is slow and these tests never log in with one.
    return User.objects.create_user(
        username=username, password=None, id_number=f"2024-{next(_counter):05d}",
        role=role, is_staff=is_staff, is_superuser=is_superuser, is_active=is_active,
    )


def make_staff(username="staff"):
    return make_user(username, role="Management", is_staff=True)


def give_points(user, staff, tier="standard"):
    """Give a user points the legitimate way: a verified return."""
    return services.record_verified_return(
        finder=user, owner=None, item_name="Umbrella", tier=tier, verified_by=staff,
        lost_item_id=next(_counter) + 1000,
    )


def make_reward(cost=80, stock=5, **kwargs):
    return Reward.objects.create(name="Canteen voucher", points_cost=cost, stock=stock, **kwargs)


def account_of(user):
    return RewardAccount.objects.get(user=user)


def request_reward(user, reward):
    return services.request_redemption(user=user, reward_id=reward.pk, idempotency_key=uuid.uuid4())[0]


# ---------------------------------------------------------------------------
# Ranks
# ---------------------------------------------------------------------------
class RankTests(TestCase):
    def test_rank_thresholds(self):
        self.assertEqual(config.get_rank(0), "Newcomer")
        self.assertEqual(config.get_rank(99), "Newcomer")
        self.assertEqual(config.get_rank(100), "Helper")
        self.assertEqual(config.get_rank(299), "Helper")
        self.assertEqual(config.get_rank(300), "Campus Hero")
        self.assertEqual(config.get_rank(749), "Campus Hero")
        self.assertEqual(config.get_rank(750), "Guardian")

    def test_progress_to_next_rank(self):
        progress = config.get_rank_progress(150)
        self.assertEqual(progress["current"], "Helper")
        self.assertEqual(progress["next"], "Campus Hero")
        self.assertEqual(progress["points_to_next"], 150)
        self.assertEqual(progress["percent"], 25)

    def test_top_rank_has_no_next(self):
        progress = config.get_rank_progress(5000)
        self.assertIsNone(progress["next"])
        self.assertEqual(progress["percent"], 100)


# ---------------------------------------------------------------------------
# Awarding points for verified returns
# ---------------------------------------------------------------------------
class ReturnAwardTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.finder = make_user("finder")
        self.owner = make_user("owner")

    def _new_return(self, **kwargs):
        data = dict(finder=self.finder, owner=self.owner, item_name="Black umbrella",
                    tier="standard", created_by=self.staff)
        data.update(kwargs)
        return services.create_return_verification(**data)

    # Requirement 1
    def test_verified_return_awards_points(self):
        v = self._new_return()
        services.verify_return(v, self.staff)
        account = account_of(self.finder)
        self.assertEqual(account.points_balance, 50)
        self.assertEqual(account.lifetime_points, 50)
        tx = PointTransaction.objects.get(account=account)
        self.assertEqual((tx.amount, tx.kind, tx.return_verification_id),
                         (50, "return_award", v.pk))
        v.refresh_from_db()
        self.assertEqual((v.status, v.points_awarded, v.reviewed_by_id), ("verified", 50, self.staff.pk))

    def test_high_value_tier_awards_100(self):
        services.verify_return(self._new_return(tier="high_value"), self.staff)
        self.assertEqual(account_of(self.finder).points_balance, 100)

    # Requirement 2
    def test_unverified_return_awards_nothing(self):
        self._new_return()
        self.assertFalse(RewardAccount.objects.filter(user=self.finder).exists())
        self.assertEqual(PointTransaction.objects.count(), 0)

    def test_rejected_return_awards_nothing(self):
        v = self._new_return()
        services.reject_return(v, self.staff, "Could not confirm")
        self.assertEqual(PointTransaction.objects.count(), 0)
        with self.assertRaises(services.InvalidTransition):
            services.verify_return(v, self.staff)
        self.assertEqual(PointTransaction.objects.count(), 0)

    # Requirement 3
    def test_same_return_cannot_award_twice(self):
        v = self._new_return()
        services.verify_return(v, self.staff)
        with self.assertRaises(services.InvalidTransition):
            services.verify_return(v, self.staff)
        self.assertEqual(account_of(self.finder).points_balance, 50)
        self.assertEqual(PointTransaction.objects.count(), 1)

    def test_database_blocks_a_second_award_for_one_return(self):
        v = self._new_return()
        services.verify_return(v, self.staff)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointTransaction.objects.create(
                account=account_of(self.finder), amount=50, kind="return_award",
                reason="duplicate", return_verification=v)

    def test_same_item_cannot_be_rewarded_twice(self):
        services.record_verified_return(finder=self.finder, owner=self.owner, item_name="Phone",
                                        tier="standard", verified_by=self.staff, lost_item_id=7)
        other = make_user("other")
        with self.assertRaises(services.RuleViolation):
            services.record_verified_return(finder=other, owner=self.owner, item_name="Phone",
                                            tier="standard", verified_by=self.staff, lost_item_id=7)
        self.assertEqual(account_of(self.finder).points_balance, 50)
        self.assertFalse(RewardAccount.objects.filter(user=other).exists())

    def test_rejected_item_can_be_recorded_again(self):
        v = self._new_return(lost_item_id=9)
        services.reject_return(v, self.staff)
        again = self._new_return(lost_item_id=9)
        services.verify_return(again, self.staff)
        self.assertEqual(account_of(self.finder).points_balance, 50)

    def test_database_blocks_two_active_records_for_one_item(self):
        self._new_return(lost_item_id=5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReturnVerification.objects.create(finder=self.finder, item_name="x", lost_item_id=5)

    def test_one_call_helper_awards_once(self):
        services.record_verified_return(finder=self.finder, owner=self.owner, item_name="Wallet",
                                        tier="high_value", verified_by=self.staff, lost_item_id=3)
        self.assertEqual(account_of(self.finder).points_balance, 100)
        self.assertEqual(ReturnVerification.objects.get().status, "verified")

    # Self-rewarding
    def test_staff_cannot_verify_their_own_return(self):
        v = self._new_return(finder=self.staff, owner=self.owner)
        with self.assertRaises(services.RuleViolation):
            services.verify_return(v, self.staff)
        self.assertEqual(PointTransaction.objects.count(), 0)

    def test_staff_cannot_verify_a_return_they_received(self):
        v = self._new_return(finder=self.finder, owner=self.staff)
        with self.assertRaises(services.RuleViolation):
            services.verify_return(v, self.staff)

    def test_one_call_helper_rolls_back_when_staff_is_the_finder(self):
        with self.assertRaises(services.RuleViolation):
            services.record_verified_return(finder=self.staff, owner=None, item_name="Pen",
                                            tier="standard", verified_by=self.staff)
        self.assertEqual(ReturnVerification.objects.count(), 0)   # nothing half-saved

    def test_finder_cannot_be_the_owner(self):
        with self.assertRaises(services.RuleViolation):
            self._new_return(owner=self.finder)

    def test_inactive_finder_cannot_be_rewarded(self):
        gone = make_user("gone", is_active=False)
        with self.assertRaises(services.RuleViolation):
            self._new_return(finder=gone)

    def test_database_blocks_verification_by_the_finder(self):
        v = self._new_return()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReturnVerification.objects.filter(pk=v.pk).update(
                status="verified", reviewed_by=self.finder, reviewed_at=timezone.now(), points_awarded=50)


# ---------------------------------------------------------------------------
# Who counts as staff
# ---------------------------------------------------------------------------
class StaffAuthorizationTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.finder = make_user("finder")
        self.v = services.create_return_verification(
            finder=self.finder, owner=None, item_name="Keys", tier="standard", created_by=self.staff)

    def test_who_is_rewards_staff(self):
        cases = [
            (make_user("normal"), False),
            (make_user("staff_wrong_role", is_staff=True), False),                   # staff, but Normal_User
            (make_user("mgmt_no_staff", role="Management"), False),                  # Management, not is_staff
            (make_user("mgmt_staff", role="Management", is_staff=True), True),
            (make_user("mgmt_inactive", role="Management", is_staff=True, is_active=False), False),
            (make_user("boss", is_superuser=True, is_staff=True), True),
            (make_user("boss_inactive", is_superuser=True, is_staff=True, is_active=False), False),
        ]
        for user, expected in cases:
            self.assertEqual(services.is_rewards_staff(user), expected, user.username)
        self.assertFalse(services.is_rewards_staff(None))

    # Requirement 4 (returns)
    def test_unauthorized_users_cannot_verify_or_reject_returns(self):
        for bad in (make_user("normal"), make_user("sw", is_staff=True),
                    make_user("mn", role="Management")):
            with self.assertRaises(PermissionDenied):
                services.verify_return(self.v, bad)
            with self.assertRaises(PermissionDenied):
                services.reject_return(self.v, bad)
            with self.assertRaises(PermissionDenied):
                services.create_return_verification(
                    finder=self.finder, owner=None, item_name="x", tier="standard", created_by=bad)
            with self.assertRaises(PermissionDenied):
                services.record_verified_return(
                    finder=self.finder, owner=None, item_name="x", tier="standard", verified_by=bad)
        self.v.refresh_from_db()
        self.assertEqual(self.v.status, "pending")
        self.assertEqual(PointTransaction.objects.count(), 0)

    # Requirement 4 (redemptions)
    def test_unauthorized_users_cannot_review_redemptions(self):
        give_points(self.finder, self.staff, "high_value")
        r = request_reward(self.finder, make_reward())
        for bad in (make_user("normal"), make_user("sw", is_staff=True)):
            for func in (services.approve_redemption, services.fulfill_redemption,
                         services.reject_redemption):
                with self.assertRaises(PermissionDenied):
                    func(r, bad)
        r.refresh_from_db()
        self.assertEqual(r.status, "pending")

    def test_staff_cannot_review_their_own_redemption(self):
        give_points(self.staff, make_user("other_staff", role="Management", is_staff=True), "high_value")
        r = request_reward(self.staff, make_reward())
        for func in (services.approve_redemption, services.reject_redemption):
            with self.assertRaises(services.RuleViolation):
                func(r, self.staff)
        r.refresh_from_db()
        self.assertEqual(r.status, "pending")


# ---------------------------------------------------------------------------
# Redemption requests
# ---------------------------------------------------------------------------
class RedemptionRequestTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.user = make_user("student")
        give_points(self.user, self.staff, "high_value")      # 100 points

    def test_request_takes_points_and_stock(self):
        reward = make_reward(cost=80, stock=5)
        r = request_reward(self.user, reward)
        account, reward = account_of(self.user), Reward.objects.get(pk=reward.pk)
        self.assertEqual((r.status, r.points_spent, r.stock_reserved), ("pending", 80, True))
        self.assertEqual((account.points_balance, account.lifetime_points), (20, 100))
        self.assertEqual(reward.stock, 4)
        hold = PointTransaction.objects.get(redemption=r)
        self.assertEqual((hold.amount, hold.kind), (-80, "redemption_hold"))

    # Requirement 5
    def test_insufficient_points_is_refused(self):
        reward = make_reward(cost=150, stock=5)
        with self.assertRaises(services.InsufficientPoints):
            request_reward(self.user, reward)
        self.assertEqual(account_of(self.user).points_balance, 100)
        self.assertEqual(Reward.objects.get(pk=reward.pk).stock, 5)
        self.assertEqual(Redemption.objects.count(), 0)

    # Requirement 6
    def test_exhausted_stock_is_refused(self):
        reward = make_reward(cost=10, stock=0)
        with self.assertRaises(services.OutOfStock):
            request_reward(self.user, reward)
        self.assertEqual(account_of(self.user).points_balance, 100)
        self.assertEqual(Redemption.objects.count(), 0)

    def test_last_item_can_be_taken_only_once(self):
        reward = make_reward(cost=10, stock=1)
        request_reward(self.user, reward)
        with self.assertRaises(services.OutOfStock):
            request_reward(self.user, reward)
        self.assertEqual(Reward.objects.get(pk=reward.pk).stock, 0)

    def test_unlimited_stock_stays_unlimited(self):
        reward = make_reward(cost=10, stock=None)
        r = request_reward(self.user, reward)
        self.assertFalse(r.stock_reserved)
        self.assertIsNone(Reward.objects.get(pk=reward.pk).stock)

    def test_inactive_or_missing_reward_is_refused(self):
        reward = make_reward(cost=10, is_active=False)
        with self.assertRaises(services.RewardUnavailable):
            request_reward(self.user, reward)
        with self.assertRaises(services.RewardUnavailable):
            services.request_redemption(user=self.user, reward_id=99999, idempotency_key=uuid.uuid4())

    def test_cannot_spend_more_than_the_balance_across_requests(self):
        reward = make_reward(cost=60, stock=None)
        request_reward(self.user, reward)
        with self.assertRaises(services.InsufficientPoints):
            request_reward(self.user, reward)
        self.assertEqual(account_of(self.user).points_balance, 40)

    # Requirement 7
    def test_double_submit_with_same_key_spends_once(self):
        reward = make_reward(cost=80, stock=5)
        key = uuid.uuid4()
        first, created1 = services.request_redemption(user=self.user, reward_id=reward.pk, idempotency_key=key)
        second, created2 = services.request_redemption(user=self.user, reward_id=reward.pk, idempotency_key=key)
        self.assertEqual((created1, created2, first.pk), (True, False, second.pk))
        self.assertEqual(account_of(self.user).points_balance, 20)
        self.assertEqual(Reward.objects.get(pk=reward.pk).stock, 4)
        self.assertEqual(Redemption.objects.count(), 1)

    def test_key_of_another_user_cannot_be_reused(self):
        reward = make_reward(cost=10)
        key = uuid.uuid4()
        services.request_redemption(user=self.user, reward_id=reward.pk, idempotency_key=key)
        thief = make_user("thief")
        give_points(thief, self.staff)
        with self.assertRaises(services.RuleViolation):
            services.request_redemption(user=thief, reward_id=reward.pk, idempotency_key=key)

    def test_price_change_later_does_not_change_the_recorded_price(self):
        reward = make_reward(cost=80)
        r = request_reward(self.user, reward)
        Reward.objects.filter(pk=reward.pk).update(points_cost=999)
        services.reject_redemption(r, self.staff)
        self.assertEqual(account_of(self.user).points_balance, 100)   # refunded 80, not 999

    def test_inactive_user_cannot_redeem(self):
        reward = make_reward()
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(PermissionDenied):
            request_reward(self.user, reward)

    def test_database_blocks_negative_or_oversized_balances(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RewardAccount.objects.filter(user=self.user).update(points_balance=F("points_balance") - 1000)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RewardAccount.objects.filter(user=self.user).update(points_balance=F("lifetime_points") + 1)


# ---------------------------------------------------------------------------
# Redemption state transitions and refunds
# ---------------------------------------------------------------------------
class RedemptionTransitionTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.user = make_user("student")
        give_points(self.user, self.staff, "high_value")      # 100 points
        self.reward = make_reward(cost=80, stock=5)
        self.r = request_reward(self.user, self.reward)

    def refunds(self):
        return PointTransaction.objects.filter(kind="redemption_refund").count()

    def balance(self):
        return account_of(self.user).points_balance

    def stock(self):
        return Reward.objects.get(pk=self.reward.pk).stock

    def test_normal_path_pending_approved_fulfilled(self):
        services.approve_redemption(self.r, self.staff)
        self.r.refresh_from_db()
        self.assertEqual((self.r.status, self.r.reviewed_by_id), ("approved", self.staff.pk))
        self.assertEqual(self.balance(), 20)            # still held
        services.fulfill_redemption(self.r, self.staff)
        self.r.refresh_from_db()
        self.assertEqual((self.r.status, self.r.fulfilled_by_id), ("fulfilled", self.staff.pk))
        self.assertIsNotNone(self.r.fulfilled_at)

    # Requirement 8: reject (pending)
    def test_reject_pending_refunds_points_and_stock_once(self):
        services.reject_redemption(self.r, self.staff, "Out of vouchers")
        self.r.refresh_from_db()
        self.assertEqual((self.r.status, self.r.refunded, self.r.staff_note), ("rejected", True, "Out of vouchers"))
        self.assertEqual((self.balance(), self.stock(), self.refunds()), (100, 5, 1))
        self.assertEqual(account_of(self.user).lifetime_points, 100)   # rank unaffected
        with self.assertRaises(services.InvalidTransition):             # a second time: refused
            services.reject_redemption(self.r, self.staff)
        self.assertEqual((self.balance(), self.stock(), self.refunds()), (100, 5, 1))

    # An approved redemption CAN be rejected (by staff), and is refunded once.
    def test_reject_approved_refunds_once(self):
        services.approve_redemption(self.r, self.staff)
        services.reject_redemption(self.r, self.staff)
        self.assertEqual((self.balance(), self.stock(), self.refunds()), (100, 5, 1))
        with self.assertRaises(services.InvalidTransition):
            services.reject_redemption(self.r, self.staff)
        self.assertEqual(self.refunds(), 1)

    # Requirement 8: cancel
    def test_user_cancel_pending_refunds_once(self):
        services.cancel_redemption(self.r, self.user)
        self.r.refresh_from_db()
        self.assertEqual((self.r.status, self.r.refunded), ("cancelled", True))
        self.assertEqual((self.balance(), self.stock(), self.refunds()), (100, 5, 1))
        with self.assertRaises(services.InvalidTransition):
            services.cancel_redemption(self.r, self.user)
        with self.assertRaises(services.InvalidTransition):
            services.reject_redemption(self.r, self.staff)     # cannot also be rejected
        self.assertEqual((self.balance(), self.refunds()), (100, 1))

    def test_user_cannot_cancel_after_approval(self):
        services.approve_redemption(self.r, self.staff)
        with self.assertRaises(services.InvalidTransition):
            services.cancel_redemption(self.r, self.user)
        self.assertEqual((self.balance(), self.refunds()), (20, 0))

    def test_only_the_owner_can_cancel(self):
        with self.assertRaises(PermissionDenied):
            services.cancel_redemption(self.r, make_user("someone_else"))
        with self.assertRaises(PermissionDenied):
            services.cancel_redemption(self.r, self.staff)
        self.assertEqual(self.balance(), 20)

    def test_fulfilled_is_final_and_never_refunded(self):
        services.approve_redemption(self.r, self.staff)
        services.fulfill_redemption(self.r, self.staff)
        for call in (lambda: services.reject_redemption(self.r, self.staff),
                     lambda: services.cancel_redemption(self.r, self.user),
                     lambda: services.approve_redemption(self.r, self.staff),
                     lambda: services.fulfill_redemption(self.r, self.staff)):
            with self.assertRaises(services.InvalidTransition):
                call()
        self.assertEqual((self.balance(), self.stock(), self.refunds()), (20, 4, 0))

    def test_invalid_moves_are_refused(self):
        with self.assertRaises(services.InvalidTransition):
            services.fulfill_redemption(self.r, self.staff)      # pending cannot be fulfilled
        services.approve_redemption(self.r, self.staff)
        with self.assertRaises(services.InvalidTransition):
            services.approve_redemption(self.r, self.staff)      # approving twice

    def test_refund_does_not_touch_stock_that_was_never_reserved(self):
        unlimited = make_reward(cost=10, stock=None)
        r = request_reward(self.user, unlimited)
        Reward.objects.filter(pk=unlimited.pk).update(stock=3)   # admin changes stock later
        services.reject_redemption(r, self.staff)
        self.assertEqual(Reward.objects.get(pk=unlimited.pk).stock, 3)

    def test_database_blocks_a_second_refund_row(self):
        services.reject_redemption(self.r, self.staff)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PointTransaction.objects.create(account=account_of(self.user), amount=80,
                                            kind="redemption_refund", reason="dup", redemption=self.r)

    def test_database_blocks_status_without_matching_refund_flag(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Redemption.objects.filter(pk=self.r.pk).update(status="rejected")   # refunded still False


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------
class LedgerTests(TestCase):
    def test_balance_always_equals_the_ledger(self):
        staff, user = make_staff(), make_user("student")
        give_points(user, staff, "high_value")
        give_points(user, staff)
        r1 = request_reward(user, make_reward(cost=70))
        request_reward(user, make_reward(cost=30))
        services.reject_redemption(r1, staff)
        account = account_of(user)
        ledger_total = PointTransaction.objects.filter(account=account).aggregate(t=Sum("amount"))["t"]
        earned = PointTransaction.objects.filter(account=account, kind="return_award").aggregate(t=Sum("amount"))["t"]
        self.assertEqual(account.points_balance, ledger_total)
        self.assertEqual(account.lifetime_points, earned)
        self.assertEqual((account.points_balance, account.lifetime_points), (120, 150))

    def test_ledger_rows_cannot_be_changed_or_deleted(self):
        staff, user = make_staff(), make_user("student")
        give_points(user, staff)
        tx = PointTransaction.objects.get()
        tx.amount = 9999
        with self.assertRaises(ValueError):
            tx.save()
        with self.assertRaises(ValueError):
            tx.delete()


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------
class LeaderboardTests(TestCase):
    def setUp(self):
        self.staff = make_staff()

    def test_no_id_numbers_or_usernames_are_exposed(self):  # Requirement 9
        user = make_user("secretusername")
        give_points(user, self.staff)
        for who in (None, user):
            board = services.get_leaderboard("all", user=who)
            text = json.dumps(board)
            self.assertNotIn(user.id_number, text)
            self.assertNotIn("secretusername", text)
            self.assertNotIn("@", text)
        self.assertEqual(services.get_leaderboard("all")["entries"][0]["name"], f"Helper #{account_of(user).pk}")

    def test_monthly_board_exposes_nothing_private_either(self):
        user = make_user("secretusername")
        give_points(user, self.staff)
        text = json.dumps(services.get_leaderboard("month", user=user))
        self.assertNotIn(user.id_number, text)
        self.assertNotIn("secretusername", text)

    def test_nickname_is_used_when_set(self):
        user = make_user("student")
        give_points(user, self.staff)
        RewardAccount.objects.filter(user=user).update(nickname="Kuya Ken")
        self.assertEqual(services.get_leaderboard()["entries"][0]["name"], "Kuya Ken")

    def test_opt_out_inactive_and_zero_point_accounts_are_hidden(self):
        hidden, gone, visible = make_user("hidden"), make_user("gone"), make_user("visible")
        for u in (hidden, gone, visible):
            give_points(u, self.staff)
        RewardAccount.objects.filter(user=hidden).update(show_on_leaderboard=False)
        User.objects.filter(pk=gone.pk).update(is_active=False)
        RewardAccount.objects.get_or_create(user=make_user("zero"))
        entries = services.get_leaderboard()["entries"]
        self.assertEqual([e["name"] for e in entries], [f"Helper #{account_of(visible).pk}"])

    def test_ties_share_a_rank_and_order_is_stable(self):
        a, b, c = make_user("a"), make_user("b"), make_user("c")
        give_points(a, self.staff); give_points(b, self.staff); give_points(c, self.staff, "high_value")
        # Make c the leader, a and b tied for second.
        entries = services.get_leaderboard()["entries"]
        self.assertEqual([e["rank"] for e in entries], [1, 2, 2])
        self.assertEqual([e["points"] for e in entries], [100, 50, 50])
        ids = [account_of(u).pk for u in (a, b)]
        self.assertEqual([e["name"] for e in entries[1:]], [f"Helper #{i}" for i in sorted(ids)])

    def test_rank_after_a_tie_skips_numbers(self):
        a, b, c = make_user("a"), make_user("b"), make_user("c")
        give_points(a, self.staff, "high_value"); give_points(b, self.staff, "high_value"); give_points(c, self.staff)
        self.assertEqual([e["rank"] for e in services.get_leaderboard()["entries"]], [1, 1, 3])

    def test_own_position_is_shown_when_outside_the_top_list(self):
        top, me = make_user("top"), make_user("me")
        give_points(top, self.staff, "high_value"); give_points(me, self.staff)
        board = services.get_leaderboard("all", user=me, limit=1)
        self.assertEqual(len(board["entries"]), 1)
        self.assertEqual((board["me"]["rank"], board["me"]["points"], board["me"]["is_me"]), (2, 50, True))

    def test_spending_points_does_not_lower_leaderboard_points(self):
        user = make_user("student")
        give_points(user, self.staff, "high_value")
        request_reward(user, make_reward(cost=90))
        self.assertEqual(services.get_leaderboard("all")["entries"][0]["points"], 100)

    def test_monthly_board_counts_only_this_months_awards(self):
        recent, old = make_user("recent"), make_user("old")
        give_points(recent, self.staff)
        give_points(old, self.staff, "high_value")
        last_month = timezone.now() - timezone.timedelta(days=45)
        PointTransaction.objects.filter(account=account_of(old)).update(created_at=last_month)
        entries = services.get_leaderboard("month")["entries"]
        self.assertEqual([e["points"] for e in entries], [50])
        self.assertEqual(entries[0]["name"], f"Helper #{account_of(recent).pk}")

    def test_bad_period_is_rejected(self):
        with self.assertRaises(ValueError):
            services.get_leaderboard("year")

    def test_nickname_validation(self):
        user = make_user("student")
        account = RewardAccount.objects.create(user=user, nickname="12345")
        with self.assertRaises(ValidationError):
            account.full_clean()
        account.nickname = f"cool-{user.id_number}"
        with self.assertRaises(ValidationError):
            account.full_clean()
        account.nickname = "Campus Pal"
        account.full_clean()


# ---------------------------------------------------------------------------
# Django Admin
# ---------------------------------------------------------------------------
class AdminAccessTests(TestCase):
    def setUp(self):
        self.staff = make_staff()
        self.finder = make_user("finder")
        self.v = services.create_return_verification(
            finder=self.finder, owner=None, item_name="Keys", tier="standard", created_by=self.staff)
        self.url = reverse("admin:rewards_returnverification_changelist")

    def test_only_rewards_staff_can_open_the_pages(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)                      # anonymous -> login
        self.client.force_login(make_user("normal"))
        self.assertEqual(self.client.get(self.url).status_code, 302)                      # not staff -> login
        self.client.force_login(make_user("staff_wrong_role", is_staff=True))
        self.assertEqual(self.client.get(self.url).status_code, 403)                      # staff, wrong role
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def _verify_action(self):
        return self.client.post(self.url, {"action": "verify_returns", "_selected_action": [self.v.pk]})

    def test_wrong_role_staff_cannot_verify_through_the_admin(self):   # Requirement 4
        self.client.force_login(make_user("staff_wrong_role", is_staff=True))
        self.assertEqual(self._verify_action().status_code, 403)
        self.v.refresh_from_db()
        self.assertEqual(self.v.status, "pending")
        self.assertEqual(PointTransaction.objects.count(), 0)

    def test_management_staff_can_verify_through_the_admin(self):
        self.client.force_login(self.staff)
        self._verify_action()
        self.v.refresh_from_db()
        self.assertEqual(self.v.status, "verified")
        self.assertEqual(account_of(self.finder).points_balance, 50)
        self._verify_action()                                           # clicking again changes nothing
        self.assertEqual(account_of(self.finder).points_balance, 50)

    def test_admin_add_form_saves_a_pending_record_without_points(self):
        self.client.force_login(self.staff)
        add_url = reverse("admin:rewards_returnverification_add")
        data = {"finder": self.finder.pk, "owner": "", "item_name": "Wallet", "lost_item_id": "42",
                "tier": "high_value", "notes": ""}
        self.assertEqual(self.client.post(add_url, data).status_code, 302)
        created = ReturnVerification.objects.get(item_name="Wallet")
        self.assertEqual((created.status, created.created_by_id), ("pending", self.staff.pk))
        self.assertEqual(PointTransaction.objects.count(), 0)
        # Same lost_item_id again: a form error, not a crash.
        response = self.client.post(add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already has an active return record")
        self.assertEqual(ReturnVerification.objects.filter(item_name="Wallet").count(), 1)

    def test_ledger_and_accounts_are_read_only_in_the_admin(self):
        self.client.force_login(self.staff)
        for name in ("pointtransaction", "rewardaccount", "redemption"):
            self.assertEqual(self.client.get(reverse(f"admin:rewards_{name}_add")).status_code, 403)

    def test_redemption_actions_work_for_staff_only(self):
        give_points(self.finder, self.staff, "high_value")
        r = request_reward(self.finder, make_reward())
        url = reverse("admin:rewards_redemption_changelist")
        data = {"action": "reject_redemptions", "_selected_action": [r.pk]}
        self.client.force_login(make_user("staff_wrong_role", is_staff=True))
        self.assertEqual(self.client.post(url, data).status_code, 403)
        r.refresh_from_db()
        self.assertEqual(r.status, "pending")
        self.client.force_login(self.staff)
        self.client.post(url, data)
        r.refresh_from_db()
        self.assertEqual((r.status, account_of(self.finder).points_balance), ("rejected", 100))


# ---------------------------------------------------------------------------
# Simultaneous requests (real threads against PostgreSQL)
# ---------------------------------------------------------------------------
class ConcurrencyTests(TransactionTestCase):
    def run_together(self, *functions):
        """Run each function in its own thread, all starting at the same moment."""
        barrier = threading.Barrier(len(functions))
        results = [None] * len(functions)

        def runner(index, function):
            try:
                barrier.wait()
                results[index] = ("ok", function())
            except Exception as exc:       # we want to inspect every outcome
                results[index] = ("error", exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=runner, args=(i, f)) for i, f in enumerate(functions)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results

    def test_two_staff_verifying_the_same_return_award_once(self):
        staff1, staff2, finder = make_staff("s1"), make_staff("s2"), make_user("finder")
        v = services.create_return_verification(
            finder=finder, owner=None, item_name="Keys", tier="standard", created_by=staff1)
        results = self.run_together(lambda: services.verify_return(v, staff1),
                                    lambda: services.verify_return(v, staff2))
        self.assertEqual(sorted(kind for kind, _ in results), ["error", "ok"])
        self.assertEqual(account_of(finder).points_balance, 50)
        self.assertEqual(PointTransaction.objects.count(), 1)

    def test_two_different_requests_cannot_overspend(self):
        staff, user = make_staff(), make_user("student")
        give_points(user, staff, "high_value")                      # 100 points
        reward = make_reward(cost=80, stock=None)
        results = self.run_together(
            lambda: services.request_redemption(user=user, reward_id=reward.pk, idempotency_key=uuid.uuid4()),
            lambda: services.request_redemption(user=user, reward_id=reward.pk, idempotency_key=uuid.uuid4()))
        self.assertEqual(sorted(kind for kind, _ in results), ["error", "ok"])
        errors = [value for kind, value in results if kind == "error"]
        self.assertIsInstance(errors[0], services.InsufficientPoints)
        self.assertEqual(account_of(user).points_balance, 20)
        self.assertEqual(Redemption.objects.count(), 1)

    def test_same_key_sent_twice_at_once_spends_once(self):
        staff, user = make_staff(), make_user("student")
        give_points(user, staff, "high_value")
        reward = make_reward(cost=80, stock=5)
        key = uuid.uuid4()
        results = self.run_together(
            lambda: services.request_redemption(user=user, reward_id=reward.pk, idempotency_key=key),
            lambda: services.request_redemption(user=user, reward_id=reward.pk, idempotency_key=key))
        self.assertEqual([kind for kind, _ in results], ["ok", "ok"])
        self.assertEqual(sorted(value[1] for _, value in results), [False, True])
        self.assertEqual(account_of(user).points_balance, 20)
        self.assertEqual(Reward.objects.get(pk=reward.pk).stock, 4)

    def test_last_unit_of_stock_goes_to_only_one_person(self):
        staff = make_staff()
        u1, u2 = make_user("u1"), make_user("u2")
        give_points(u1, staff); give_points(u2, staff)
        reward = make_reward(cost=10, stock=1)
        results = self.run_together(
            lambda: services.request_redemption(user=u1, reward_id=reward.pk, idempotency_key=uuid.uuid4()),
            lambda: services.request_redemption(user=u2, reward_id=reward.pk, idempotency_key=uuid.uuid4()))
        self.assertEqual(sorted(kind for kind, _ in results), ["error", "ok"])
        self.assertEqual(Reward.objects.get(pk=reward.pk).stock, 0)
        self.assertEqual(Redemption.objects.count(), 1)

    def test_reject_and_cancel_at_once_refund_only_once(self):
        staff, user = make_staff(), make_user("student")
        give_points(user, staff, "high_value")
        r = request_reward(user, make_reward(cost=80, stock=5))
        results = self.run_together(lambda: services.reject_redemption(r, staff),
                                    lambda: services.cancel_redemption(r, user))
        self.assertEqual(sorted(kind for kind, _ in results), ["error", "ok"])
        self.assertEqual(account_of(user).points_balance, 100)
        self.assertEqual(PointTransaction.objects.filter(kind="redemption_refund").count(), 1)
        self.assertEqual(Reward.objects.get().stock, 5)


# ---------------------------------------------------------------------------
# Student and management pages (login + authorization)
# ---------------------------------------------------------------------------
class RewardsPageTests(TestCase):
    def setUp(self):
        self.user = make_user("student")
        self.staff = make_staff("mgr")
        self.reward = make_reward(cost=50, stock=3)

    def test_guest_is_redirected_from_student_pages(self):
        for name in ("dashboard", "catalog", "history", "leaderboard", "profile"):
            response = self.client.get(reverse(f"rewards:{name}"))
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login/", response.url)

    def test_logged_in_user_can_open_student_pages(self):
        self.client.force_login(self.user)
        for name in ("dashboard", "catalog", "history", "leaderboard", "profile"):
            response = self.client.get(reverse(f"rewards:{name}"))
            self.assertEqual(response.status_code, 200, msg=name)

    def test_leaderboard_page_hides_private_identifiers(self):
        give_points(self.user, self.staff)
        account = account_of(self.user)
        account.nickname = "BlueFox"
        account.save(update_fields=["nickname"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("rewards:leaderboard"))
        body = response.content.decode()
        # Public ranking block must use nickname only (nav may show own username privately).
        start = body.find('class="rw-leaderboard"')
        end = body.find("</ol>", start)
        board_html = body[start:end]
        self.assertIn("BlueFox", board_html)
        self.assertNotIn(self.user.username, board_html)
        self.assertNotIn(self.user.id_number, body)

    def test_redeem_and_cancel_through_views(self):
        give_points(self.user, self.staff)  # 50 pts
        self.client.force_login(self.user)
        key = uuid.uuid4()
        response = self.client.post(
            reverse("rewards:redeem", args=[self.reward.pk]),
            {"idempotency_key": str(key)},
        )
        self.assertEqual(response.status_code, 302)
        redemption = Redemption.objects.get(idempotency_key=key)
        self.assertEqual(redemption.status, "pending")
        self.assertEqual(account_of(self.user).points_balance, 0)

        response = self.client.post(reverse("rewards:cancel", args=[redemption.pk]))
        self.assertEqual(response.status_code, 302)
        redemption.refresh_from_db()
        self.assertEqual(redemption.status, "cancelled")
        self.assertEqual(account_of(self.user).points_balance, 50)

    def test_normal_user_cannot_open_management_pages(self):
        self.client.force_login(self.user)
        for name in ("manage_returns", "manage_redemptions", "manage_return_create"):
            response = self.client.get(reverse(f"rewards:{name}"))
            self.assertEqual(response.status_code, 403, msg=name)

    def test_staff_can_verify_return_through_management_view(self):
        finder = make_user("finder2")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("rewards:manage_return_create"), {
            "finder": finder.pk,
            "owner": "",
            "item_name": "Campus ID",
            "lost_item_id": "",
            "tier": "high_value",
            "notes": "Handed to guard desk",
        })
        self.assertEqual(response.status_code, 302)
        verification = ReturnVerification.objects.get(item_name="Campus ID")
        self.assertEqual(verification.status, "pending")

        response = self.client.post(
            reverse("rewards:manage_return_verify", args=[verification.pk])
        )
        self.assertEqual(response.status_code, 302)
        verification.refresh_from_db()
        self.assertEqual(verification.status, "verified")
        self.assertEqual(account_of(finder).points_balance, 100)
        self.assertEqual(account_of(finder).lifetime_points, 100)