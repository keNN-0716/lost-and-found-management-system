"""
Student and Management views for the rewards app.

Points, stock, and status changes always go through rewards.services —
views never edit balances directly.
"""
import uuid
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import config, services
from .forms import NicknameForm, RedeemForm, ReturnVerificationCreateForm, StaffNoteForm
from .models import PointTransaction, Redemption, Reward, RewardAccount, ReturnVerification


def rewards_staff_required(view_func):
    """Server-side gate for Management staff actions (not just hiding UI)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not services.is_rewards_staff(request.user):
            return HttpResponseForbidden(
                "Only active Management staff can access this page."
            )
        return view_func(request, *args, **kwargs)

    return login_required(_wrapped)


def _get_or_create_account(user):
    account, _ = RewardAccount.objects.get_or_create(user=user)
    return account


# ---------------------------------------------------------------------------
# Student pages
# ---------------------------------------------------------------------------
@login_required
@require_GET
def dashboard(request):
    account = _get_or_create_account(request.user)
    progress = config.get_rank_progress(account.lifetime_points)
    recent_tx = (
        PointTransaction.objects.filter(account=account)
        .select_related("return_verification", "redemption__reward")[:8]
    )
    recent_redemptions = (
        Redemption.objects.filter(account=account)
        .select_related("reward")[:5]
    )
    return render(request, "rewards/dashboard.html", {
        "account": account,
        "progress": progress,
        "recent_transactions": recent_tx,
        "recent_redemptions": recent_redemptions,
        "tier_points": config.TIER_POINTS,
        "is_rewards_staff": services.is_rewards_staff(request.user),
    })


@login_required
@require_GET
def catalog(request):
    account = _get_or_create_account(request.user)
    rewards = list(Reward.objects.filter(is_active=True))
    # Each card needs its own key so redeeming different rewards is independent.
    reward_cards = [
        {
            "reward": reward,
            "idempotency_key": uuid.uuid4(),
            "shortfall": max(0, reward.points_cost - account.points_balance),
            "can_afford": account.points_balance >= reward.points_cost,
        }
        for reward in rewards
    ]
    return render(request, "rewards/catalog.html", {
        "account": account,
        "reward_cards": reward_cards,
    })


@login_required
@require_POST
def redeem(request, reward_id):
    form = RedeemForm(request.POST)
    if not form.is_valid():
        messages.error(request, "That redemption request was not valid. Please try again.")
        return redirect("rewards:catalog")

    try:
        redemption, created = services.request_redemption(
            user=request.user,
            reward_id=reward_id,
            idempotency_key=form.cleaned_data["idempotency_key"],
        )
    except PermissionDenied as exc:
        messages.error(request, str(exc) or "You cannot redeem right now.")
        return redirect("rewards:catalog")
    except services.InsufficientPoints as exc:
        messages.warning(request, str(exc))
        return redirect("rewards:catalog")
    except (services.RewardUnavailable, services.OutOfStock, services.RuleViolation) as exc:
        messages.error(request, str(exc))
        return redirect("rewards:catalog")

    if created:
        messages.success(
            request,
            f"Redemption requested for “{redemption.reward.name}”. "
            f"{redemption.points_spent} points are on hold until staff review it.",
        )
    else:
        messages.info(request, "That redemption was already submitted.")
    return redirect("rewards:history")


@login_required
@require_POST
def cancel(request, redemption_id):
    redemption = get_object_or_404(
        Redemption.objects.select_related("account"),
        pk=redemption_id,
    )
    try:
        services.cancel_redemption(redemption, request.user)
    except PermissionDenied:
        messages.error(request, "You can only cancel your own pending redemptions.")
        return redirect("rewards:history")
    except services.RewardsError as exc:
        messages.error(request, str(exc))
        return redirect("rewards:history")

    messages.success(request, "Redemption cancelled. Your points have been refunded.")
    return redirect("rewards:history")


@login_required
@require_GET
def history(request):
    account = _get_or_create_account(request.user)
    tab = request.GET.get("tab", "transactions")
    if tab not in ("transactions", "redemptions"):
        tab = "transactions"

    tx_qs = (
        PointTransaction.objects.filter(account=account)
        .select_related("return_verification", "redemption__reward")
    )
    red_qs = Redemption.objects.filter(account=account).select_related("reward")

    tx_page = Paginator(tx_qs, 15).get_page(request.GET.get("page"))
    red_page = Paginator(red_qs, 15).get_page(request.GET.get("page"))

    return render(request, "rewards/history.html", {
        "account": account,
        "tab": tab,
        "tx_page": tx_page,
        "red_page": red_page,
    })


@login_required
@require_GET
def leaderboard(request):
    period = request.GET.get("period", "all")
    if period not in ("all", "month"):
        period = "all"
    board = services.get_leaderboard(period=period, user=request.user)
    account = _get_or_create_account(request.user)
    return render(request, "rewards/leaderboard.html", {
        "account": account,
        "period": period,
        "entries": board["entries"],
        "me": board["me"],
    })


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    account = _get_or_create_account(request.user)
    if request.method == "POST":
        form = NicknameForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, "Your leaderboard preferences were saved.")
            return redirect("rewards:profile")
    else:
        form = NicknameForm(instance=account)
    return render(request, "rewards/profile.html", {
        "account": account,
        "form": form,
        "progress": config.get_rank_progress(account.lifetime_points),
    })


# ---------------------------------------------------------------------------
# Management pages (server-side staff checks)
# ---------------------------------------------------------------------------
@rewards_staff_required
@require_GET
def manage_returns(request):
    pending = (
        ReturnVerification.objects.filter(status=ReturnVerification.Status.PENDING)
        .select_related("finder", "owner", "created_by")
    )
    recent = (
        ReturnVerification.objects.exclude(status=ReturnVerification.Status.PENDING)
        .select_related("finder", "owner", "reviewed_by")[:20]
    )
    return render(request, "rewards/manage_returns.html", {
        "pending_returns": pending,
        "recent_returns": recent,
        "tier_points": config.TIER_POINTS,
        "note_form": StaffNoteForm(),
    })


@rewards_staff_required
@require_http_methods(["GET", "POST"])
def manage_return_create(request):
    if request.method == "POST":
        form = ReturnVerificationCreateForm(request.POST)
        if form.is_valid():
            try:
                verification = services.create_return_verification(
                    finder=form.cleaned_data["finder"],
                    owner=form.cleaned_data.get("owner"),
                    item_name=form.cleaned_data["item_name"],
                    tier=form.cleaned_data["tier"],
                    created_by=request.user,
                    lost_item_id=form.cleaned_data.get("lost_item_id"),
                    notes=form.cleaned_data.get("notes") or "",
                )
            except (services.RewardsError, PermissionDenied) as exc:
                messages.error(request, str(exc) or "Could not create return record.")
            else:
                messages.success(
                    request,
                    f"Return “{verification.item_name}” recorded as pending. "
                    "Verify it to award points.",
                )
                return redirect("rewards:manage_returns")
    else:
        form = ReturnVerificationCreateForm()
    return render(request, "rewards/manage_return_create.html", {"form": form})


@rewards_staff_required
@require_POST
def manage_return_verify(request, verification_id):
    verification = get_object_or_404(ReturnVerification, pk=verification_id)
    try:
        services.verify_return(verification, request.user)
    except (services.RewardsError, PermissionDenied) as exc:
        messages.error(request, str(exc) or "Could not verify this return.")
    else:
        messages.success(
            request,
            f"Return verified. Points awarded to the finder.",
        )
    return redirect("rewards:manage_returns")


@rewards_staff_required
@require_POST
def manage_return_reject(request, verification_id):
    verification = get_object_or_404(ReturnVerification, pk=verification_id)
    form = StaffNoteForm(request.POST)
    notes = form.cleaned_data.get("note", "") if form.is_valid() else ""
    try:
        services.reject_return(verification, request.user, notes=notes)
    except (services.RewardsError, PermissionDenied) as exc:
        messages.error(request, str(exc) or "Could not reject this return.")
    else:
        messages.info(request, "Return rejected. No points were awarded.")
    return redirect("rewards:manage_returns")


@rewards_staff_required
@require_GET
def manage_redemptions(request):
    pending = (
        Redemption.objects.filter(
            status__in=[Redemption.Status.PENDING, Redemption.Status.APPROVED]
        )
        .select_related("account__user", "reward")
        .order_by("status", "created_at")
    )
    recent = (
        Redemption.objects.filter(
            status__in=[
                Redemption.Status.FULFILLED,
                Redemption.Status.REJECTED,
                Redemption.Status.CANCELLED,
            ]
        )
        .select_related("account__user", "reward")[:20]
    )
    return render(request, "rewards/manage_redemptions.html", {
        "queue": pending,
        "recent": recent,
        "note_form": StaffNoteForm(),
    })


@rewards_staff_required
@require_POST
def manage_redemption_approve(request, redemption_id):
    redemption = get_object_or_404(Redemption, pk=redemption_id)
    try:
        services.approve_redemption(redemption, request.user)
    except (services.RewardsError, PermissionDenied) as exc:
        messages.error(request, str(exc) or "Could not approve.")
    else:
        messages.success(request, "Redemption approved. Mark fulfilled when handed over.")
    return redirect("rewards:manage_redemptions")


@rewards_staff_required
@require_POST
def manage_redemption_fulfill(request, redemption_id):
    redemption = get_object_or_404(Redemption, pk=redemption_id)
    try:
        services.fulfill_redemption(redemption, request.user)
    except (services.RewardsError, PermissionDenied) as exc:
        messages.error(request, str(exc) or "Could not fulfill.")
    else:
        messages.success(request, "Redemption marked fulfilled. Points are not refunded.")
    return redirect("rewards:manage_redemptions")


@rewards_staff_required
@require_POST
def manage_redemption_reject(request, redemption_id):
    redemption = get_object_or_404(Redemption, pk=redemption_id)
    form = StaffNoteForm(request.POST)
    note = form.cleaned_data.get("note", "") if form.is_valid() else ""
    try:
        services.reject_redemption(redemption, request.user, note=note)
    except (services.RewardsError, PermissionDenied) as exc:
        messages.error(request, str(exc) or "Could not reject.")
    else:
        messages.info(request, "Redemption rejected and points refunded.")
    return redirect("rewards:manage_redemptions")
