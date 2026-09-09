"""Speculative trade rumors. These are fabricated, unlike every other feature.

Normally fires on a coin flip in the Tuesday/Thursday morning windows, so
some weeks bring two rumors and some bring none. Tagged distinctly from real
news (RUMOR MILL, not BREAKING) so nobody mistakes a rumor for an actual
trade.

Odds and frequency both track the league's trade deadline, since that's when
real trade buzz peaks:
  - more than 2 weeks out: odds ramp from RUMOR_CHANCE_MIN up to
    RUMOR_CHANCE_PEAK, still on the normal Tue/Thu cadence.
  - the week before and the week of the deadline: odds hold at
    RUMOR_CHANCE_PEAK, with extra days in play (Sun/Tue/Wed/Thu) so the mill
    fires more often, roughly 3-4 times that week.
  - after the deadline: back down to RUMOR_CHANCE_POST, back to twice a week.
    Content shifts too. Trades are no longer possible once the deadline has
    passed, so the mill pivots to contract-extension and release/cut buzz
    instead of trade speculation.
Falls back to a flat RUMOR_CHANCE all season if the league has no trade
deadline configured.
"""
import random
from collections import defaultdict
from datetime import datetime

from .. import state
from ..formatter import _player, _team

NAME = "rumors"

# Statuses that make a player a bad subject for a rumor (already gone/hurt).
SIDELINED = {"OUT", "INJURY_RESERVE", "SUSPENSION"}

BUYER_LEDES = [
    "RUMOR MILL: {a} has discussed {player} with {b}. Nothing is imminent.",
    "RUMOR MILL: {a} has checked in with {b} about {player}. No deal is in place.",
    "RUMOR MILL: {a} has interest in {b}'s {player}. Worth monitoring.",
]

SELL_LEDES = [
    "RUMOR MILL: {a} has fielded interest in {player} after a slow start.",
    "RUMOR MILL: {b} has checked in on {a}'s {player}. No deal is in place.",
    "RUMOR MILL: {a} could be open to moving {player}. Nothing is imminent.",
]

HOLE_LEDES = [
    "RUMOR MILL: With {reason} sidelined, {a} has checked with {b} about {player}.",
    "RUMOR MILL: {a} is looking for depth after losing {reason}. "
    "{b}'s {player} is one name to watch.",
]

RIVALRY_LEDES = [
    "RUMOR MILL: {a} and {b} have discussed a {player}-for-{player_b} framework.",
    "RUMOR MILL: {a} and {b} have talked about a deal centered on "
    "{player} and {player_b}. Nothing is imminent.",
]

# Post-deadline: trades are off the table, so the mill shifts to real-team
# contract buzz about the players still sitting on fantasy rosters.
EXTENSION_LEDES = [
    "RUMOR MILL: {player} and his club could discuss an extension soon.",
    "RUMOR MILL: {a}'s {player} could be in line for a new deal.",
    "RUMOR MILL: {player} is one extension candidate to monitor.",
]

RELEASE_LEDES = [
    "RUMOR MILL: {player} is on the roster bubble after a slow stretch.",
    "RUMOR MILL: {a}'s {player} could become a cap-casualty candidate.",
    "RUMOR MILL: {player}'s roster spot with {a} is worth monitoring.",
]

# Pure comedy, untethered from actual roster logic. Locker-room gossip and
# front-office nonsense rather than trade speculation. Still gated by the
# same odds/cadence and anti-repeat window as everything else here.
TABLOID_LEDES = [
    "RUMOR MILL: {a}'s GM reportedly consulted a psychic before benching {player} this week.",
    "RUMOR MILL: {a} keeps a shrine to {player} in the basement. Candles, the works.",
    "RUMOR MILL: {a} reportedly set this week's lineup by rock-paper-scissors, with {player}'s spot on the line.",
    "RUMOR MILL: {a}'s GM texts {player} good luck before every game. {player} has never replied.",
    "RUMOR MILL: {a}'s locker room has reportedly been tense since a recent front-office divorce.",
    "RUMOR MILL: {a} would reportedly trade {player} for one good beer.",
    "RUMOR MILL: {a} blames a curse for {player}'s slow start, specifically a fantasy loss "
    "from three years ago nobody has let go of.",
    "RUMOR MILL: {a}'s GM has reportedly not slept a full night since drafting {player}.",
    "RUMOR MILL: {a} keeps a vision board with {player}'s stat line on it. It is not going well.",
]

TABLOID_DUO_LEDES = [
    "RUMOR MILL: {a} and {b}'s GMs reportedly haven't spoken since a group chat trade fell "
    "through in Week 2.",
    "RUMOR MILL: {a} and {b} are said to be in a running feud over who copied whose team "
    "name first.",
    "RUMOR MILL: {a}'s GM reportedly muted {b}'s GM for a full week over a waiver claim.",
    "RUMOR MILL: {a} and {b} reportedly have a standing bet that's gotten uncomfortably "
    "personal.",
]

_HISTORY_LIMIT = 6  # keeps subjects from repeating too soon


def enabled(cfg):
    return cfg.FEATURES["rumors"]


# The window covering "the week before" and "the week of" the deadline.
# two weeks is close enough to both without needing calendar-week math.
_PEAK_WINDOW_DAYS = 14

NORMAL_DAYS = (1, 3)        # Tue, Thu: the standard cadence
PEAK_DAYS = (6, 1, 2, 3)    # Sun, Tue, Wed, Thu: extra slots during the peak window


def _slot(now):
    return now.strftime("%a").lower()  # 'sun', 'mon', 'tue', ...; unique per weekday


def _period_key(lg, slot):
    return f"{lg.year}-w{lg.current_week}-{slot}"


def _deadline(lg, cfg):
    ms = getattr(lg.settings, "trade_deadline", 0)
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=cfg.TZ)


def _days_until_deadline(lg, cfg, now):
    """None if no deadline is set; otherwise (possibly negative) days remaining."""
    deadline = _deadline(lg, cfg)
    if deadline is None:
        return None
    return (deadline - now).total_seconds() / 86400


def _active_days(lg, cfg, now):
    days_left = _days_until_deadline(lg, cfg, now)
    if days_left is not None and 0 <= days_left <= _PEAK_WINDOW_DAYS:
        return PEAK_DAYS
    return NORMAL_DAYS


def should_run(now, st, lg, cfg):
    if lg.current_week < 1:
        return False
    if now.weekday() not in _active_days(lg, cfg, now):
        return False
    start, end = cfg.RUMOR_WINDOW
    if not (start <= now.hour < end):
        return False
    return not state.already_ran(st, NAME, _period_key(lg, _slot(now)))


def _chance(lg, cfg, now):
    """Odds the rumor mill fires today, ramping toward the trade deadline."""
    days_left = _days_until_deadline(lg, cfg, now)
    if days_left is None:
        return cfg.RUMOR_CHANCE  # no deadline configured; flat rate all season
    if days_left < 0:
        return cfg.RUMOR_CHANCE_POST
    if days_left <= _PEAK_WINDOW_DAYS:
        return cfg.RUMOR_CHANCE_PEAK

    ramp_days = cfg.RUMOR_RAMP_WEEKS * 7
    progress = 1 - max(0.0, min(1.0, (days_left - _PEAK_WINDOW_DAYS) / ramp_days))
    return cfg.RUMOR_CHANCE_MIN + (cfg.RUMOR_CHANCE_PEAK - cfg.RUMOR_CHANCE_MIN) * progress


def _skill(p):
    return p.position not in ("K", "D/ST", "DST")


def _healthy(p):
    return (p.injuryStatus or "").upper() not in SIDELINED


def _recent_ids(st):
    ids = set()
    for entry in st.get("rumor_history", [])[-_HISTORY_LIMIT:]:
        ids.update(entry.get("teams", []))
    return ids


def _buyer_rumor(buyers, sellers, excluded):
    pairs = [
        (a, b) for a in buyers for b in sellers
        if a.team_id != b.team_id and a.team_id not in excluded and b.team_id not in excluded
    ]
    random.shuffle(pairs)
    for team_a, team_b in pairs:
        pool = [p for p in team_b.roster if _skill(p) and _healthy(p)]
        if pool:
            player = max(pool, key=lambda p: p.total_points)
            return {"kind": "buyer", "a": team_a, "b": team_b, "player": player}
    return None


def _flagged(all_teams, *, under):
    """Skill-position, healthy players whose output diverges from projection:
    underperformers (under=True) or overperformers (under=False). Basis for
    both 'sell' trade rumors and, post-deadline, release/extension rumors.
    """
    flagged = []
    for team in all_teams:
        for p in team.roster:
            if not _skill(p) or not _healthy(p) or p.projected_avg_points <= 5:
                continue
            if under and p.avg_points < 0.8 * p.projected_avg_points:
                flagged.append((team, p))
            elif not under and p.avg_points > 1.2 * p.projected_avg_points:
                flagged.append((team, p))
    return flagged


def _sell_rumor(all_teams, buyers, excluded):
    flagged = [(t, p) for t, p in _flagged(all_teams, under=True) if t.team_id not in excluded]
    if not flagged:
        return None
    team_a, player = max(flagged, key=lambda tp: tp[1].projected_avg_points)
    pool = [t for t in buyers if t.team_id != team_a.team_id and t.team_id not in excluded]
    if not pool:
        return None
    team_b = random.choice(pool)
    return {"kind": "sell", "a": team_a, "b": team_b, "player": player}


def _hole_rumor(all_teams, excluded):
    for team in random.sample(all_teams, len(all_teams)):
        if team.team_id in excluded:
            continue
        by_pos = defaultdict(list)
        for p in team.roster:
            if _skill(p):
                by_pos[p.position].append(p)
        for pos, players in by_pos.items():
            if not players or any(_healthy(p) for p in players):
                continue  # not actually a hole; someone healthy is still there
            donors = [
                t for t in all_teams
                if t.team_id != team.team_id and t.team_id not in excluded
                and any(_skill(p) and p.position == pos and _healthy(p) for p in t.roster)
            ]
            if not donors:
                continue
            team_b = random.choice(donors)
            donor_pool = [p for p in team_b.roster if p.position == pos and _healthy(p)]
            player = max(donor_pool, key=lambda p: p.total_points)
            return {
                "kind": "hole", "a": team, "b": team_b,
                "player": player, "reason": players[0],
            }
    return None


def _rivalry_rumor(all_teams, excluded):
    ranked = sorted(all_teams, key=lambda t: (t.wins, t.points_for), reverse=True)
    pairs = [
        (ranked[i], ranked[i + 1]) for i in range(len(ranked) - 1)
        if abs(ranked[i].wins - ranked[i + 1].wins) <= 1
        and ranked[i].team_id not in excluded and ranked[i + 1].team_id not in excluded
    ]
    random.shuffle(pairs)
    for team_a, team_b in pairs:
        pool_a = [p for p in team_a.roster if _skill(p) and _healthy(p)]
        pool_b = [p for p in team_b.roster if _skill(p) and _healthy(p)]
        if pool_a and pool_b:
            return {
                "kind": "rivalry", "a": team_a, "b": team_b,
                "player": random.choice(pool_a), "player_b": random.choice(pool_b),
            }
    return None


def _tabloid_rumor(all_teams, excluded):
    for team in random.sample(all_teams, len(all_teams)):
        if team.team_id in excluded:
            continue
        pool = [p for p in team.roster if _skill(p) and _healthy(p)]
        if pool:
            return {"kind": "tabloid", "a": team, "player": random.choice(pool)}
    return None


def _tabloid_duo_rumor(all_teams, excluded):
    pool = [t for t in all_teams if t.team_id not in excluded]
    if len(pool) < 2:
        return None
    team_a, team_b = random.sample(pool, 2)
    return {"kind": "tabloid_duo", "a": team_a, "b": team_b}


def _pick_rumor(lg, st):
    all_teams = lg.teams
    ranked = all_teams
    if lg.current_week > 1:
        try:
            ranked = [team for _score, team in lg.power_rankings(lg.current_week - 1)] or all_teams
        except Exception:
            ranked = sorted(all_teams, key=lambda t: (t.wins, t.points_for), reverse=True)
    thirds = max(1, len(ranked) // 3)
    buyers, sellers = ranked[:thirds], ranked[-thirds:]
    excluded = _recent_ids(st)

    candidates = [
        c for c in (
            _buyer_rumor(buyers, sellers, excluded),
            _sell_rumor(all_teams, buyers, excluded),
            _hole_rumor(all_teams, excluded),
            _rivalry_rumor(all_teams, excluded),
            _tabloid_rumor(all_teams, excluded),
            _tabloid_duo_rumor(all_teams, excluded),
        ) if c
    ]
    return random.choice(candidates) if candidates else None


def _release_rumor(all_teams, excluded):
    flagged = [(t, p) for t, p in _flagged(all_teams, under=True) if t.team_id not in excluded]
    if not flagged:
        return None
    team, player = max(flagged, key=lambda tp: tp[1].projected_avg_points)
    return {"kind": "release", "a": team, "player": player}


def _extension_rumor(all_teams, excluded):
    flagged = [(t, p) for t, p in _flagged(all_teams, under=False) if t.team_id not in excluded]
    if not flagged:
        return None
    team, player = max(flagged, key=lambda tp: tp[1].avg_points - tp[1].projected_avg_points)
    return {"kind": "extension", "a": team, "player": player}


def _pick_contract_rumor(lg, st):
    all_teams = lg.teams
    excluded = _recent_ids(st)
    candidates = [
        c for c in (
            _release_rumor(all_teams, excluded),
            _extension_rumor(all_teams, excluded),
        ) if c
    ]
    return random.choice(candidates) if candidates else None


def _format(rumor):
    a = _team(rumor["a"])
    if rumor["kind"] == "tabloid_duo":
        return random.choice(TABLOID_DUO_LEDES).format(a=a, b=_team(rumor["b"]))

    player = _player(rumor["player"])
    if rumor["kind"] == "tabloid":
        return random.choice(TABLOID_LEDES).format(a=a, player=player)
    if rumor["kind"] == "extension":
        return random.choice(EXTENSION_LEDES).format(a=a, player=player)
    if rumor["kind"] == "release":
        return random.choice(RELEASE_LEDES).format(a=a, player=player)

    b = _team(rumor["b"])
    if rumor["kind"] == "buyer":
        return random.choice(BUYER_LEDES).format(a=a, b=b, player=player)
    if rumor["kind"] == "sell":
        return random.choice(SELL_LEDES).format(a=a, b=b, player=player)
    if rumor["kind"] == "hole":
        return random.choice(HOLE_LEDES).format(
            a=a, b=b, player=player, reason=_player(rumor["reason"])
        )
    return random.choice(RIVALRY_LEDES).format(
        a=a, b=b, player=player, player_b=_player(rumor["player_b"])
    )


def run(lg, st, cfg):
    now = datetime.now(cfg.TZ)
    slot = _slot(now)
    period_key = _period_key(lg, slot)
    state.mark_ran(st, NAME, period_key)  # mark regardless of outcome; a miss stays silent

    if random.random() > _chance(lg, cfg, now):
        return []

    days_left = _days_until_deadline(lg, cfg, now)
    past_deadline = days_left is not None and days_left < 0
    rumor = _pick_contract_rumor(lg, st) if past_deadline else _pick_rumor(lg, st)
    if not rumor:
        return []

    teams = [rumor["a"].team_id] + ([rumor["b"].team_id] if "b" in rumor else [])
    history = st.setdefault("rumor_history", [])
    history.append({
        "week": lg.current_week,
        "teams": teams,
        "player": rumor["player"].playerId if "player" in rumor else None,
    })
    st["rumor_history"] = history[-_HISTORY_LIMIT:]

    return [_format(rumor)]
