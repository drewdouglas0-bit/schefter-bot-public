"""Tracks what the bot has already announced.

ESPN's activity feed has no stable per-event ID, so we fingerprint each activity
by its timestamp plus the (team, action, player) rows it contains. That is stable
across polls and unique enough in practice.

Other features namespace their own state under their feature name.
"""
import hashlib
import json

from . import config

_MAX_SEEN = 500  # plenty of history to dedupe against; keeps the file small

_DEFAULT = {
    "seen": [],        # transaction fingerprints
    "seeded": False,
    "injuries": {},    # playerId -> last announced status
    "last_run": {},    # feature -> period key it last fired for
    "rankings": {},    # team_id -> last week's rank, for movement arrows
    "rumor_history": [],  # recent {week, teams: [id, id], player} entries, for anti-repeat
    "draft_lottery": {},  # season (str) -> cached [team_id, ...] draft order
}


def fingerprint(activity) -> str:
    rows = sorted(
        f"{getattr(team, 'team_id', '')}|{action}|{getattr(player, 'playerId', player)}"
        for team, action, player, _bid in activity.actions
    )
    raw = f"{activity.date}::" + "::".join(rows)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def load() -> dict:
    if not config.STATE_FILE.exists():
        return dict(_DEFAULT, seen=[], injuries={}, last_run={}, rankings={})
    with open(config.STATE_FILE) as f:
        st = json.load(f)
    for key, default in _DEFAULT.items():  # tolerate state written by older versions
        st.setdefault(key, default() if callable(default) else type(default)())
    return st


def save(st: dict) -> None:
    st["seen"] = st["seen"][-_MAX_SEEN:]
    tmp = config.STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(st, f, indent=2)
    tmp.replace(config.STATE_FILE)  # atomic, so a crash mid-write can't corrupt state


def already_ran(st: dict, feature: str, period_key: str) -> bool:
    """True if `feature` has already fired for this period (e.g. this week)."""
    return st["last_run"].get(feature) == period_key


def mark_ran(st: dict, feature: str, period_key: str) -> None:
    st["last_run"][feature] = period_key
