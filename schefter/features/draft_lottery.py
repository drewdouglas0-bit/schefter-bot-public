"""On-demand draft lottery. Every team has the same odds for every pick.

Never fires on a scheduled poll; run it explicitly when you're ready to set
next season's draft order:

    python -m schefter.main --only draft_lottery --force --send

Results are cached per season so re-running it (e.g. after a crash mid-send,
or just to re-post the order) reposts the same result instead of re-rolling.
"""
import random

from ..formatter import _team

NAME = "draft_lottery"


def enabled(cfg):
    return cfg.FEATURES["draft_lottery"]


def should_run(now, st, lg, cfg):
    return False  # on-demand only; invoke with --only draft_lottery --force


def _period_key(lg):
    return str(lg.year)


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _messages(order, lg):
    """Reveal one pick at a time, last pick first. order[0] is pick 1."""
    league = getattr(lg.settings, "name", None) or "Fantasy League"
    return [
        f"Draft order: {_team(order[pick - 1])} holds the {_ordinal(pick)} "
        f"overall pick in the {lg.year} {league} Draft."
        for pick in range(len(order), 0, -1)
    ]


def run(lg, st, cfg):
    period_key = _period_key(lg)
    results = st.setdefault("draft_lottery", {})

    cached = results.get(period_key)
    if cached:
        by_id = {t.team_id: t for t in lg.teams}
        order = [by_id[tid] for tid in cached if tid in by_id]
        if len(order) == len(cached):
            return _messages(order, lg)
        # roster of teams changed since the cached run; fall through and reroll

    order = list(lg.teams)
    random.shuffle(order)
    results[period_key] = [team.team_id for team in order]

    return _messages(order, lg)
