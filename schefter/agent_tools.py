"""Narrow, read-only ESPN tools exposed to the conversational agent."""
from datetime import datetime

from . import config, draft, espn, formatter, history, polls, trades


def _value(obj, *names, default=None):
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _team(team) -> dict:
    return {
        "id": _value(team, "team_id", "teamId"),
        "name": _value(team, "team_name", "teamName", default="Unknown"),
        "owner": _value(team, "owner", default=""),
        "record": {
            "wins": _value(team, "wins", default=0),
            "losses": _value(team, "losses", default=0),
            "ties": _value(team, "ties", default=0),
        },
        "standing": _value(team, "standing"),
        "points_for": _value(team, "points_for", "pointsFor"),
    }


def league_overview() -> dict:
    league = espn.get_league()
    settings = getattr(league, "settings", None)
    return {
        "league": _value(settings, "name", default="Fantasy league"),
        "season": config.SEASON,
        "current_week": _value(league, "current_week", default=None),
        "teams": [_team(team) for team in league.teams],
    }


def recent_transactions(limit: int = 10) -> dict:
    limit = max(1, min(int(limit), 25))
    rows = []
    for activity in espn.recent_activity(size=limit):
        text = formatter.format_activity(activity)
        if text:
            rows.append({
                "time": datetime.fromtimestamp(activity.date / 1000, config.TZ).isoformat(),
                "summary": text,
            })
    return {"transactions": rows[-limit:]}


def team_roster(team_name: str) -> dict:
    league = espn.get_league()
    needle = team_name.casefold().strip()
    candidates = [
        team for team in league.teams
        if needle in str(_value(team, "team_name", "teamName", default="")).casefold()
        or needle in str(_value(team, "owner", default="")).casefold()
    ]
    if not candidates:
        return {"error": f"No team or owner matched {team_name!r}"}
    if len(candidates) > 1:
        return {"error": "More than one team matched", "matches": [_team(t) for t in candidates]}
    team = candidates[0]
    players = []
    for player in getattr(team, "roster", []):
        players.append({
            "name": _value(player, "name", default="Unknown"),
            "position": _value(player, "position"),
            "nfl_team": _value(player, "proTeam", "pro_team"),
            "lineup_slot": _value(player, "lineupSlot", "lineup_slot"),
            "injury_status": _value(player, "injuryStatus", "injury_status"),
            "points": _value(player, "total_points", "totalPoints"),
            "projected_points": _value(player, "projected_total_points", "projectedTotalPoints"),
        })
    return {"team": _team(team), "roster": players}


def matchups(week: int | None = None) -> dict:
    league = espn.get_league()
    target_week = int(week or _value(league, "current_week", default=1))
    games = []
    for game in league.scoreboard(week=target_week):
        home = getattr(game, "home_team", None)
        away = getattr(game, "away_team", None)
        games.append({
            "home": _value(home, "team_name", default="TBD"),
            "home_score": _value(game, "home_score"),
            "away": _value(away, "team_name", default="TBD"),
            "away_score": _value(game, "away_score"),
        })
    return {"week": target_week, "matchups": games}


TOOLS = [
    {
        "type": "function",
        "name": "create_poll",
        "description": (
            "Post a group poll when explicitly asked, or when the group is directly asked to "
            "choose among two or more concrete options. Not for advice or hypotheticals."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "minLength": 1, "maxLength": 300},
                "options": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 120},
                    "minItems": 2,
                    "maxItems": 9,
                },
            },
            "required": ["question", "options"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_poll_results",
        "description": "Report the current tally for the open poll, or the last poll if none is open.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "close_poll",
        "description": "Close the open poll and report its final tally. Only when the user asks to close or end it.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_draft_results",
        "description": (
            "Draft picks for a season, defaulting to the current one. Filter by team or "
            "manager, player, or round; a full draft is hundreds of picks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "year": {"type": ["integer", "null"]},
                "team": {"type": ["string", "null"]},
                "player": {"type": ["string", "null"]},
                "round": {"type": ["integer", "null"]},
            },
            "required": ["year", "team", "player", "round"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_league_history",
        "description": "Champions and final standings per completed season.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_all_time_standings",
        "description": (
            "Career records across completed seasons, aggregated and ranked. Use for any "
            "all-time or best/worst-ever question. Set sort_by to what was asked."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": ["wins", "losses", "win_pct", "worst",
                             "championships", "points_for", "average_finish"],
                },
                "limit": {"type": ["integer", "null"]},
            },
            "required": ["sort_by", "limit"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_league_records",
        "description": (
            "Single-game superlatives: biggest blowout, highest or lowest score, closest finish."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["blowout", "highest_score", "lowest_score", "closest"],
                },
                "limit": {"type": ["integer", "null"]},
            },
            "required": ["kind", "limit"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_head_to_head",
        "description": (
            "All-time record between two managers. Accepts a person or any team name they have used."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "manager_a": {"type": "string"},
                "manager_b": {"type": "string"},
            },
            "required": ["manager_a", "manager_b"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_manager_record",
        "description": (
            "One manager's career record, championships, and finish per season. Accepts a "
            "person or any team name they have used."
        ),
        "parameters": {
            "type": "object",
            "properties": {"manager": {"type": "string"}},
            "required": ["manager"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "create_trade_proposal",
        "description": "Create a trade proposal only on an explicit request. The sender's mapped team offers.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_team": {"type": "string"},
                "offered_players": {"type": "array", "items": {"type": "string"}},
                "requested_players": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["target_team", "offered_players", "requested_players"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "respond_to_trade",
        "description": "Accept or reject a pending trade for the sender. Requires an explicit accept/yes or reject/no.",
        "parameters": {
            "type": "object",
            "properties": {
                "proposal_id": {"type": ["string", "null"]},
                "decision": {"type": "string", "enum": ["accept", "reject"]},
            },
            "required": ["proposal_id", "decision"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_my_pending_trades",
        "description": "List pending trade proposals involving the current sender.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_league_overview",
        "description": "Get current league standings, records, owners, and scoring totals.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_recent_transactions",
        "description": "Get recent adds, drops, waiver claims, and trades from this ESPN league.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 25}},
            "required": ["limit"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_team_roster",
        "description": "Get a fantasy team's current roster by team name or owner name.",
        "parameters": {
            "type": "object",
            "properties": {"team_name": {"type": "string"}},
            "required": ["team_name"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_matchups",
        "description": "Get fantasy matchups and scores for a week.",
        "parameters": {
            "type": "object",
            "properties": {"week": {"type": ["integer", "null"], "minimum": 1}},
            "required": ["week"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def call(name: str, arguments: dict, actor: str | None = None):
    functions = {
        "create_poll": lambda: polls.create(arguments["question"], arguments["options"]),
        "get_poll_results": lambda: polls.results(),
        "close_poll": lambda: polls.close(),
        "get_draft_results": lambda: draft.results(
            year=arguments.get("year"),
            team=arguments.get("team"),
            player=arguments.get("player"),
            round_num=arguments.get("round"),
        ),
        "get_league_history": lambda: history.summary(),
        "get_all_time_standings": lambda: history.all_time_standings(
            sort_by=arguments.get("sort_by") or "wins",
            limit=arguments.get("limit") or 10,
        ),
        "get_league_records": lambda: history.league_records(
            kind=arguments.get("kind") or "blowout",
            limit=arguments.get("limit") or 5,
        ),
        "get_head_to_head": lambda: history.head_to_head(
            arguments["manager_a"], arguments["manager_b"]
        ),
        "get_manager_record": lambda: history.manager_record(arguments["manager"]),
        "get_league_overview": lambda: league_overview(),
        "get_recent_transactions": lambda: recent_transactions(arguments["limit"]),
        "get_team_roster": lambda: team_roster(arguments["team_name"]),
        "get_matchups": lambda: matchups(arguments.get("week")),
        "create_trade_proposal": lambda: trades.create(
            actor or "", arguments["target_team"], arguments["offered_players"], arguments["requested_players"]
        ),
        "respond_to_trade": lambda: trades.respond(
            actor or "", arguments["decision"], arguments.get("proposal_id")
        ),
        "get_my_pending_trades": lambda: trades.pending(actor or ""),
    }
    if name not in functions:
        return {"error": f"Unknown tool: {name}"}
    try:
        return functions[name]()
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
