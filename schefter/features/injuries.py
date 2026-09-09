"""Injury status changes on rostered players."""
import random

from ..formatter import _player, _src

NAME = "injuries"

# Statuses worth interrupting 13 people for. QUESTIONABLE is deliberately
# excluded by default; half the league carries that tag by Friday.
LOUD = {
    "OUT": "is not expected to play",
    "DOUBTFUL": "is doubtful",
    "INJURY_RESERVE": "is being placed on injured reserve",
    "SUSPENSION": "has been suspended",
    "DAY_TO_DAY": "is considered day-to-day",
}
QUESTIONABLE = {"QUESTIONABLE": "is questionable"}

# Anything in here means "fine". Moving into it is a return, not an injury.
HEALTHY = {"ACTIVE", "NORMAL", "", None}

RETURN_LEDES = [
    "{team}'s {player} has been upgraded and is expected to play.",
    "{player} is off the injury report and expected to play for {team}.",
    "{team} is expected to have {player} back.",
]


def enabled(cfg):
    return cfg.FEATURES["injuries"]


def should_run(now, st, lg, cfg):
    return lg.current_week > 0  # nothing to report in the offseason


def run(lg, st, cfg):
    """Compares every rostered player's status against what we last announced."""
    watched = dict(LOUD)
    if cfg.ANNOUNCE_QUESTIONABLE:
        watched.update(QUESTIONABLE)

    seen_now = {}
    messages = []

    for team in lg.teams:
        for p in team.roster:
            pid = str(p.playerId)
            status = (p.injuryStatus or "").upper()
            seen_now[pid] = status
            previous = st["injuries"].get(pid)

            if previous == status:
                continue

            if status in watched:
                verb = watched[status]
                messages.append(
                    f"{team.team_name}'s {_player(p)} {verb}, {_src()}"
                )
            elif status in HEALTHY and previous and previous not in HEALTHY:
                messages.append(
                    random.choice(RETURN_LEDES).format(
                        team=team.team_name, player=_player(p), src=_src()
                    )
                )

    # Replace wholesale so dropped players don't linger in state forever.
    st["injuries"] = seen_now
    return messages
