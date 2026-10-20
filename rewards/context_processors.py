"""Template context shared by the application shell."""
from . import services


def rewards_nav(request):
    user = getattr(request, "user", None)
    return {
        "is_rewards_staff": bool(user and services.is_rewards_staff(user)),
    }
