"""Turns ESPN activity rows into compact NFL transaction-wire blurbs."""
import random
from collections import defaultdict

ADD_ACTIONS = {"FA ADDED", "WAIVER ADDED"}
DROP_ACTIONS = {"DROPPED"}

# Attribute the actual data source without pretending the bot has human sources.
SOURCING = [
    "per ESPN.",
    "per the league transaction log.",
    "league records show.",
]

FA_LEDES = [
    "ESPN: {team} added {player}.",
    "{team} signed {player}, {src}",
    "{team} added {player}, {src}",
]

WAIVER_LEDES = [
    "{team} was awarded {player} off waivers{bid}.",
    "ESPN: {team} added {player} via waivers{bid}.",
    "Waiver claim: {team} gets {player}{bid}.",
]

DROP_ONLY_LEDES = [
    "{team} released {player}.",
    "ESPN: {team} waived {player}.",
    "{team} waived {player}, {src}",
]


def _src():
    return random.choice(SOURCING)


def _player(player) -> str:
    """Return a compact position/name/team label, with an ID fallback."""
    name = getattr(player, "name", None)
    if not name:
        return f"player #{player}"
    pos = getattr(player, "position", "")
    pro = getattr(player, "proTeam", "")
    label = f"{pos} {name}".strip()
    if pro and pro not in ("None", "FA"):
        label += f" ({pro})"
    return label


def _team(team) -> str:
    return getattr(team, "team_name", None) or "An unknown team"


def _players(players) -> str:
    labels = [_player(p) for p in players]
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _format_trade(actions) -> str:
    """Trades arrive as TRADE_SENT/TRADE_RECEIVED pairs; report by who receives what."""
    receiving = defaultdict(list)
    teams = []
    for team, action, player, _bid in actions:
        if action == "TRADE_RECEIVED" and team:
            name = _team(team)
            if name not in receiving:
                teams.append(name)
            receiving[name].append(player)

    if len(teams) < 2:
        # One-sided data: ESPN occasionally omits the counterparty.
        who = teams[0] if teams else "A team"
        haul = _players(receiving[who]) if teams else "multiple players"
        return f"Trade: {who} acquired {haul}, {_src()}"

    return (
        f"Trade: {teams[0]} acquired {_players(receiving[teams[0]])} "
        f"from {teams[1]} in exchange for {_players(receiving[teams[1]])}, {_src()}"
    )


def format_digest(activities) -> str:
    """Used when a poll turns up a burst too big to narrate one at a time."""
    adds = trades = drops = 0
    for activity in activities:
        if any(a[1].startswith("TRADE") for a in activity.actions):
            trades += 1
            continue
        for _team, action, _player, _bid in activity.actions:
            if action in ADD_ACTIONS:
                adds += 1
            elif action in DROP_ACTIONS:
                drops += 1

    bits = []
    if trades:
        bits.append(f"{trades} trade{'s' if trades > 1 else ''}")
    if adds:
        bits.append(f"{adds} signing{'s' if adds > 1 else ''}")
    if drops:
        bits.append(f"{drops} release{'s' if drops > 1 else ''}")
    summary = ", ".join(bits) if bits else f"{len(activities)} moves"

    return (
        f"League activity: {summary} in the last few minutes. "
        "The transaction log has the full rundown."
    )


def format_activity(activity) -> str | None:
    """One activity -> one chat message. Returns None if there's nothing worth posting."""
    actions = activity.actions
    if any(a[1] in ("TRADE_SENT", "TRADE_RECEIVED") for a in actions):
        return _format_trade(actions)

    adds, drops, bids = defaultdict(list), defaultdict(list), {}
    waiver_teams = set()
    for team, action, player, bid in actions:
        if not team:
            continue
        name = _team(team)
        if action in ADD_ACTIONS:
            adds[name].append(player)
            if action == "WAIVER ADDED":
                waiver_teams.add(name)
                if bid:
                    bids[name] = bid
        elif action in DROP_ACTIONS:
            drops[name].append(player)

    if not adds and not drops:
        return None

    chunks = []
    for name in adds:
        is_waiver = name in waiver_teams
        bid = f" for ${bids[name]} of FAAB" if name in bids else ""
        template = random.choice(WAIVER_LEDES if is_waiver else FA_LEDES)
        chunks.append(
            template.format(
                team=name, player=_players(adds[name]), bid=bid, src=_src()
            )
        )
        # A drop by the same team in the same activity is the corresponding move.
        if name in drops:
            chunks.append(
                f"In a corresponding move, {name} released {_players(drops.pop(name))}."
            )

    # Standalone drops (no matching add) get their own blurb.
    for name, players in drops.items():
        chunks.append(
            random.choice(DROP_ONLY_LEDES).format(
                team=name, player=_players(players), src=_src()
            )
        )

    return " ".join(chunks)
