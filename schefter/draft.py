"""Draft results for the current or any completed season.

A full draft is 224-448 picks, far more than belongs in a chat reply or a
model's context, so every lookup is filtered and the response is capped.
"""
from . import config, espn

MAX_PICKS = 60

_cache: dict[int, object] = {}


def _league(year: int | None):
    """Leagues are memoized: a completed draft never changes."""
    current = espn.get_league()
    if year is None or int(year) == current.year:
        if not current.draft:
            current.refresh_draft()
        return current
    year = int(year)
    if year not in _cache:
        from espn_api.football import League

        _cache[year] = League(
            league_id=config.LEAGUE_ID,
            year=year,
            espn_s2=config.ESPN_S2,
            swid=config.SWID,
        )
    return _cache[year]


def _manager(team) -> str:
    owners = getattr(team, "owners", None) or []
    first = owners[0] if owners and isinstance(owners[0], dict) else {}
    return " ".join(
        part for part in (first.get("firstName"), first.get("lastName")) if part
    ).strip()


def _matches_team(team, needle: str) -> bool:
    """Match a team by its name that season or by the manager's name."""
    candidates = [str(getattr(team, "team_name", "")), _manager(team)]
    for candidate in candidates:
        folded = candidate.casefold()
        if not folded:
            continue
        if needle == folded or needle in folded.replace("'", "").split():
            return True
        if len(needle) >= 3 and needle in folded:
            return True
    return False


def results(
    year: int | None = None,
    team: str | None = None,
    player: str | None = None,
    round_num: int | None = None,
) -> dict:
    """Draft picks, filtered by season, team/manager, player, or round."""
    try:
        league = _league(year)
    except Exception as exc:
        return {"error": f"Could not load the {year} draft ({type(exc).__name__})"}

    # espn-api's refresh_draft() appends to league.draft instead of replacing
    # it, so a league object it has been called on twice reports every pick
    # twice. The league is a long-lived singleton in the listener, so dedupe
    # by slot rather than trusting nothing ever refreshed it.
    picks, seen = [], set()
    for pick in getattr(league, "draft", []) or []:
        slot = (int(getattr(pick, "round_num", 0) or 0), int(getattr(pick, "round_pick", 0) or 0))
        if slot in seen:
            continue
        seen.add(slot)
        picks.append(pick)

    if not picks:
        return {
            "year": getattr(league, "year", year),
            "picks": [],
            "note": "That season has no draft results; it may not have been drafted yet",
        }

    rounds = max(int(getattr(p, "round_num", 0) or 0) for p in picks)
    matching = []
    for pick in picks:
        pick_team = getattr(pick, "team", None)
        if round_num is not None and int(getattr(pick, "round_num", 0) or 0) != int(round_num):
            continue
        if team and not (pick_team is not None and _matches_team(pick_team, team.casefold().strip())):
            continue
        if player and player.casefold().strip() not in str(getattr(pick, "playerName", "")).casefold():
            continue
        round_number = int(getattr(pick, "round_num", 0) or 0)
        round_pick = int(getattr(pick, "round_pick", 0) or 0)
        matching.append({
            "round": round_number,
            "pick": round_pick,
            "overall": (round_number - 1) * len(league.teams) + round_pick,
            "player": getattr(pick, "playerName", "") or f"player #{getattr(pick, 'playerId', '?')}",
            "team": getattr(pick_team, "team_name", "Unknown team"),
            "manager": _manager(pick_team) if pick_team is not None else "",
        })

    if not matching:
        asked = ", ".join(
            part for part in (
                f"team {team!r}" if team else "",
                f"player {player!r}" if player else "",
                f"round {round_num}" if round_num is not None else "",
            ) if part
        )
        return {
            "year": league.year,
            "picks": [],
            "note": f"No draft picks matched {asked}" if asked else "No draft picks found",
        }

    matching.sort(key=lambda row: row["overall"])
    payload = {
        "year": league.year,
        "rounds": rounds,
        "total_matching": len(matching),
        "picks": matching[:MAX_PICKS],
    }
    if len(matching) > MAX_PICKS:
        payload["note"] = (
            f"Showing the first {MAX_PICKS} of {len(matching)} picks. "
            "Narrow it by team, player, or round."
        )
    return payload
