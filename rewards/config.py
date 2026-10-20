"""
rewards/config.py  (NEW FILE)

Every tunable rule of the rewards module lives here, so a number is never
copied into several files. To change a point value or a rank threshold, edit
this file only.
"""

# --- Points -----------------------------------------------------------------
# Staff choose a "tier" when verifying a return. They never type a number.
TIER_POINTS = {
    "standard": 50,      # e.g. umbrella, bottle, notebook
    "high_value": 100,   # e.g. ID, phone, wallet, laptop
}

# --- Ranks ------------------------------------------------------------------
# (rank name, lifetime points needed). Keep this list sorted from low to high.
# Rank is based on LIFETIME points, so spending points never lowers your rank.
RANKS = [
    ("Newcomer", 0),
    ("Helper", 100),        # 2 standard returns
    ("Campus Hero", 300),   # 6 standard returns
    ("Guardian", 750),      # 15 standard returns
]

# --- Leaderboard and profile ------------------------------------------------
LEADERBOARD_SIZE = 10
NICKNAME_MAX_LENGTH = 30

# --- Staff ------------------------------------------------------------------
# Must match LostAndFound.models.CustomUser.Roles.MANAGEMENT. We compare the
# plain text so the rewards app does not import from LostAndFound.
MANAGEMENT_ROLE = "Management"


def _rank_index(lifetime_points):
    """Position in RANKS of the highest rank reached."""
    index = 0
    for i, (_name, needed) in enumerate(RANKS):
        if lifetime_points >= needed:
            index = i
    return index


def get_rank(lifetime_points):
    """Return the rank name for a number of lifetime points."""
    return RANKS[_rank_index(lifetime_points)][0]


def get_rank_progress(lifetime_points):
    """
    Return a dict used by the dashboard progress bar:
    current rank, next rank, points still needed, and percent (0-100).
    """
    index = _rank_index(lifetime_points)
    current_name, current_at = RANKS[index]

    if index == len(RANKS) - 1:  # already the top rank
        return {"current": current_name, "next": None, "next_at": None,
                "points_to_next": 0, "percent": 100}

    next_name, next_at = RANKS[index + 1]
    percent = int((lifetime_points - current_at) * 100 / (next_at - current_at))
    return {"current": current_name, "next": next_name, "next_at": next_at,
            "points_to_next": next_at - lifetime_points, "percent": percent}