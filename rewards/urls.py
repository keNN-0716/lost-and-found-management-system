"""
URL patterns for student-facing and Management rewards pages.
"""
from django.urls import path

from . import views

app_name = "rewards"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("catalog/", views.catalog, name="catalog"),
    path("redeem/<int:reward_id>/", views.redeem, name="redeem"),
    path("cancel/<int:redemption_id>/", views.cancel, name="cancel"),
    path("history/", views.history, name="history"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("profile/", views.profile, name="profile"),
    # Management
    path("manage/returns/", views.manage_returns, name="manage_returns"),
    path("manage/returns/new/", views.manage_return_create, name="manage_return_create"),
    path(
        "manage/returns/<int:verification_id>/verify/",
        views.manage_return_verify,
        name="manage_return_verify",
    ),
    path(
        "manage/returns/<int:verification_id>/reject/",
        views.manage_return_reject,
        name="manage_return_reject",
    ),
    path("manage/redemptions/", views.manage_redemptions, name="manage_redemptions"),
    path(
        "manage/redemptions/<int:redemption_id>/approve/",
        views.manage_redemption_approve,
        name="manage_redemption_approve",
    ),
    path(
        "manage/redemptions/<int:redemption_id>/fulfill/",
        views.manage_redemption_fulfill,
        name="manage_redemption_fulfill",
    ),
    path(
        "manage/redemptions/<int:redemption_id>/reject/",
        views.manage_redemption_reject,
        name="manage_redemption_reject",
    ),
]
