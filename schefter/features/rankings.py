"""Weekly power rankings, with week-over-week movement to argue about."""
from .. import state
from ..formatter import _src

NAME = "rankings"


def enabled(cfg):
    return cfg.FEATURES["rankings"]


def _week(lg):
    return lg.current_week - 1


def _period_key(lg):
    return f"{lg.year}-w{_week(lg)}"


def should_run(now, st, lg, cfg):
    if _week(lg) < 1:
        return False
    if now.weekday() != 1:  # Tuesday, same slot as the recap
        return False
    start, end = cfg.RECAP_WINDOW
    if not (start <= now.hour < end):
        return False
    return not state.already_ran(st, NAME, _period_key(lg))


def _arrow(team_id, rank, previous):
    was = previous.get(str(team_id))
    if was is None:
        return "  "
    delta = was - rank
    if delta > 0:
        return f"▲{delta}"
    if delta < 0:
        return f"▼{abs(delta)}"
    return " ="


def run(lg, st, cfg):
    week = _week(lg)
    if week < 1:
        return []  # guards --force too; should_run isn't the only safety net
    try:
        ranked = lg.power_rankings(week)
    except Exception:
        return []

    state.mark_ran(st, NAME, _period_key(lg))
    if not ranked:
        return []

    previous = st.get("rankings", {})
    lines = [f"Power rankings after Week {week}:", ""]
    current = {}

    for i, (score, team) in enumerate(ranked, start=1):
        current[str(team.team_id)] = i
        arrow = _arrow(team.team_id, i, previous)
        lines.append(
            f"{i:>2}. {arrow}  {team.team_name}  "
            f"({team.wins}-{team.losses}, {float(score):.1f})"
        )

    st["rankings"] = current

    biggest = None
    for tid, rank in current.items():
        if tid in previous:
            delta = previous[tid] - rank
            if biggest is None or abs(delta) > abs(biggest[1]):
                biggest = (tid, delta)

    if biggest and biggest[1]:
        team = next((t for t in lg.teams if str(t.team_id) == biggest[0]), None)
        if team:
            direction = "surging" if biggest[1] > 0 else "in free fall"
            lines.append(f"\n{team.team_name} is {direction}, {_src()}")

    return ["\n".join(lines)]
