"""Sunday pre-kickoff sweep: who has a dead player in their starting lineup.

The single most useful thing this bot does. It stops people from losing a week
to a bye they forgot about.
"""
from datetime import datetime

from .. import state
from ..formatter import _player

NAME = "inactives"

BENCH_SLOTS = {"BE", "IR"}
DEAD_STATUSES = {"OUT", "INJURY_RESERVE", "SUSPENSION", "DOUBTFUL"}


def enabled(cfg):
    return cfg.FEATURES["inactives"]


def _period_key(lg):
    return f"{lg.year}-w{lg.current_week}"


def should_run(now, st, lg, cfg):
    if lg.current_week < 1:
        return False
    if now.weekday() != 6:  # Sunday
        return False
    start, end = cfg.INACTIVE_WINDOW
    if not (start <= now.hour < end):
        return False
    return not state.already_ran(st, NAME, _period_key(lg))


def _problems(lineup):
    """Starters who are OUT, suspended, or on bye."""
    found = []
    for p in lineup:
        if p.slot_position in BENCH_SLOTS:
            continue
        status = (getattr(p, "injuryStatus", "") or "").upper()
        if getattr(p, "on_bye_week", False):
            found.append((p, "on a BYE"))
        elif status in DEAD_STATUSES:
            found.append((p, status.replace("_", " ")))
    return found


def run(lg, st, cfg):
    if lg.current_week < 1:
        return []  # guards --force too; should_run isn't the only safety net
    try:
        boxes = lg.box_scores()
    except Exception:
        return []  # lineups aren't published yet; try again next poll

    offenders = []
    for box in boxes:
        for team, lineup in ((box.home_team, box.home_lineup),
                             (box.away_team, box.away_lineup)):
            if team and lineup:
                probs = _problems(lineup)
                if probs:
                    offenders.append((team, probs))

    state.mark_ran(st, NAME, _period_key(lg))

    if not offenders:
        return ["Lineup check: Every starting lineup is clean this week."]

    lines = ["Lineup alert: Kickoff is close and these starters need attention:", ""]
    for team, probs in offenders:
        for p, why in probs:
            lines.append(f"• {team.team_name}: {_player(p)} is {why}")
    lines += ["", "Managers have been notified."]
    return ["\n".join(lines)]
