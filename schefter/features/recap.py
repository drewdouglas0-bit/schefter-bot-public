"""Tuesday morning recap of the week that just finished, bench blunders included."""
from .. import state
from ..formatter import _player, _src

NAME = "recap"

BENCH_SLOTS = {"BE", "IR"}


def enabled(cfg):
    return cfg.FEATURES["recap"]


def _week(lg):
    """The week that just completed."""
    return lg.current_week - 1


def _period_key(lg):
    return f"{lg.year}-w{_week(lg)}"


def should_run(now, st, lg, cfg):
    if _week(lg) < 1:
        return False
    if now.weekday() != 1:  # Tuesday, after Monday night wraps
        return False
    start, end = cfg.RECAP_WINDOW
    if not (start <= now.hour < end):
        return False
    return not state.already_ran(st, NAME, _period_key(lg))


def _bench_points(lineup):
    """Points scored by benched players who could have started.

    Approximation: sums the bench, ignoring IR. Good enough to start an argument,
    which is the point.
    """
    return sum(p.points for p in lineup
               if p.slot_position == "BE" and p.points)


def _best_bench_player(lineup):
    bench = [p for p in lineup if p.slot_position == "BE" and p.points]
    return max(bench, key=lambda p: p.points) if bench else None


def run(lg, st, cfg):
    week = _week(lg)
    if week < 1:
        return []  # guards --force too; should_run isn't the only safety net
    try:
        boxes = lg.box_scores(week)
    except Exception:
        return []

    state.mark_ran(st, NAME, _period_key(lg))

    results, scores, benches = [], [], []
    for box in boxes:
        if not (box.home_team and box.away_team):
            continue  # bye
        results.append(box)
        scores.append((box.home_team, box.home_score))
        scores.append((box.away_team, box.away_score))
        for team, lineup in ((box.home_team, box.home_lineup),
                             (box.away_team, box.away_lineup)):
            benches.append((team, _bench_points(lineup), _best_bench_player(lineup)))

    if not results:
        return []

    lines = [f"📋 WEEK {week} FINAL", ""]
    for box in results:
        if box.home_score >= box.away_score:
            win, wpts, lose, lpts = (box.home_team, box.home_score,
                                     box.away_team, box.away_score)
        else:
            win, wpts, lose, lpts = (box.away_team, box.away_score,
                                     box.home_team, box.home_score)
        lines.append(f"{win.team_name} def. {lose.team_name}, {wpts:.1f}-{lpts:.1f}")

    top_team, top_pts = max(scores, key=lambda s: s[1])
    low_team, low_pts = min(scores, key=lambda s: s[1])
    margins = [(abs(b.home_score - b.away_score), b) for b in results]
    closest = min(margins, key=lambda m: m[0])
    blowout = max(margins, key=lambda m: m[0])

    lines += [
        "",
        f"High scorer: {top_team.team_name} ({top_pts:.1f})",
        f"Low scorer: {low_team.team_name} ({low_pts:.1f})",
        f"Closest call: {closest[1].home_team.team_name} / "
        f"{closest[1].away_team.team_name} decided by {closest[0]:.1f}",
        f"Biggest beatdown: {blowout[0]:.1f} points",
    ]

    worst = max(benches, key=lambda b: b[1], default=None)
    if worst and worst[1] > 0:
        team, pts, best = worst
        line = f"\n{team.team_name} left {pts:.1f} points on the bench"
        if best:
            line += f", including {_player(best)} at {best.points:.1f}"
        lines.append(line + f", {_src()}")

    return ["\n".join(lines)]
