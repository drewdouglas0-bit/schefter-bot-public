"""Completed-season records for the league, cached to disk.

Managers are keyed by ESPN owner id, never team name. Team names churn between
seasons (for example, a fictional manager renames "Alpha Squad" to "Alpha Crew"),
so a name-keyed history silently loses a manager's earlier years.

Only seasons ESPN reports as previous are included. The live season's results
already reach the agent through the ordinary league tools, and folding them in
here would invalidate the cache every week.
"""
import json
from datetime import datetime

from . import config, db, espn

CACHE_VERSION = 1


def _owner(team) -> dict:
    owners = getattr(team, "owners", None) or []
    first = owners[0] if owners and isinstance(owners[0], dict) else {}
    owner_id = str(first.get("id") or "").strip()
    name = " ".join(
        part for part in (first.get("firstName"), first.get("lastName")) if part
    ).strip()
    return {"id": owner_id, "name": name or "Unknown manager"}


def _season_record(year: int) -> dict:
    """One completed season: final finish plus every team's week-by-week results."""
    from espn_api.football import League

    league = League(
        league_id=config.LEAGUE_ID,
        year=year,
        espn_s2=config.ESPN_S2,
        swid=config.SWID,
    )
    regular_weeks = int(getattr(league.settings, "reg_season_count", 0) or 0)

    standings, results, managers = [], [], {}
    for team in league.teams:
        owner = _owner(team)
        if not owner["id"]:
            continue
        managers[owner["id"]] = {"name": owner["name"], "team": team.team_name}
        standings.append({
            "owner": owner["id"],
            "team": team.team_name,
            "final_standing": int(getattr(team, "final_standing", 0) or 0),
            "wins": int(getattr(team, "wins", 0) or 0),
            "losses": int(getattr(team, "losses", 0) or 0),
            "points_for": round(float(getattr(team, "points_for", 0) or 0), 2),
        })

        schedule = list(getattr(team, "schedule", []) or [])
        scores = list(getattr(team, "scores", []) or [])
        for index, opponent in enumerate(schedule):
            week = index + 1
            opponent_owner = _owner(opponent) if opponent is not None else {"id": ""}
            if not opponent_owner["id"] or opponent_owner["id"] == owner["id"]:
                continue  # a playoff bye lists no real opponent
            score = float(scores[index]) if index < len(scores) else 0.0
            opponent_scores = list(getattr(opponent, "scores", []) or [])
            opponent_score = float(opponent_scores[index]) if index < len(opponent_scores) else 0.0
            if score == 0.0 and opponent_score == 0.0:
                continue  # unplayed week
            results.append({
                "owner": owner["id"],
                "opponent": opponent_owner["id"],
                "week": week,
                "regular_season": week <= regular_weeks,
                "points": round(score, 2),
                "opponent_points": round(opponent_score, 2),
            })

    standings.sort(key=lambda row: row["final_standing"] or 99)
    return {"standings": standings, "results": results, "managers": managers}


def build(force: bool = False) -> dict:
    """Fetch every completed season and cache it. Reuses the cache unless stale."""
    league = espn.get_league()
    seasons = sorted(int(y) for y in (getattr(league, "previousSeasons", None) or []))

    cached = _read_cache()
    if not force and cached and cached.get("seasons") == seasons:
        return cached

    years, managers = {}, {}
    for year in seasons:
        season = _season_record(year)
        years[str(year)] = {
            "standings": season["standings"],
            "results": season["results"],
        }
        for owner_id, info in season["managers"].items():
            entry = managers.setdefault(owner_id, {"name": info["name"], "teams": {}})
            entry["teams"][str(year)] = info["team"]
            if info["name"] != "Unknown manager":
                entry["name"] = info["name"]

    # The live season's team names make a manager recognizable today.
    for team in league.teams:
        owner = _owner(team)
        if owner["id"]:
            entry = managers.setdefault(owner["id"], {"name": owner["name"], "teams": {}})
            entry["teams"][str(league.year)] = team.team_name

    data = {
        "version": CACHE_VERSION,
        "built_at": datetime.now(config.TZ).isoformat(),
        "league_id": config.LEAGUE_ID,
        "seasons": seasons,
        "managers": managers,
        "years": years,
    }
    _write_cache(data)
    db.replace_seasons(years, managers)
    return data


def _ensure_db() -> None:
    """The SQL tables are built from the same fetch as the JSON cache."""
    if db.stored_seasons() != sorted(int(y) for y in (build().get("seasons") or [])):
        data = build(force=True)
        db.replace_seasons(data["years"], data["managers"])


def all_time_standings(sort_by: str = "wins", limit: int | None = 10) -> dict:
    """Ranked career table. Metrics are named so a request maps to one defined thing."""
    _ensure_db()
    rows = db.all_time_standings(sort_by=sort_by, limit=limit)
    if not rows:
        return {"error": "No completed seasons are stored for this league yet"}
    # Name managers through the same helper the rest of this module uses, so a
    # person is not "Ann Alpha (Old Team)" here and "(Alpha Squad)" in the champion
    # line. The database only holds completed seasons; _display knows the
    # current one.
    data = build()
    return {
        "sorted_by": sort_by if sort_by in db.SORTS else "wins",
        "seasons_covered": db.stored_seasons(),
        "standings": [
            {
                "rank": index,
                "manager": _display(data, row["owner_id"]),
                "record": f"{row['wins']}-{row['losses']}" + (f"-{row['ties']}" if row["ties"] else ""),
                "wins": row["wins"],
                "losses": row["losses"],
                "win_pct": row["win_pct"],
                "points_for": row["points_for"],
                "championships": row["championships"],
                "average_finish": row["average_finish"],
                "seasons": row["seasons"],
            }
            for index, row in enumerate(rows, start=1)
        ],
    }


def league_records(kind: str = "blowout", limit: int = 5) -> dict:
    _ensure_db()
    rows = db.extremes(kind=kind, limit=limit)
    if not rows:
        return {"error": "No completed seasons are stored for this league yet"}
    return {"kind": kind, "seasons_covered": db.stored_seasons(), "records": rows}


def _read_cache() -> dict | None:
    if not config.HISTORY_CACHE_FILE.exists():
        return None
    try:
        with open(config.HISTORY_CACHE_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if data.get("version") != CACHE_VERSION or data.get("league_id") != config.LEAGUE_ID:
        return None
    return data


def _write_cache(data: dict) -> None:
    tmp = config.HISTORY_CACHE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(config.HISTORY_CACHE_FILE)


def _display(data: dict, owner_id: str) -> str:
    manager = data["managers"].get(owner_id, {})
    teams = manager.get("teams", {})
    current = teams.get(max(teams, default=""), "")
    name = manager.get("name", "Unknown manager")
    return f"{name} ({current})" if current else name


def resolve_manager(data: dict, query: str) -> str | None:
    """Match a person's name or any team name they have ever used.

    Tiered so a short first name still works ("Bo" matches "Bo Beta") without a
    loose substring rule pulling in the wrong manager. An ambiguous query
    resolves to nothing rather than guessing.
    """
    needle = " ".join(str(query).split()).casefold()
    if not needle:
        return None

    exact, word, partial = set(), set(), set()
    for owner_id, manager in data["managers"].items():
        candidates = [manager.get("name", "")] + list(manager.get("teams", {}).values())
        for candidate in candidates:
            # ESPN stores stray double spaces ("Alex  Terriquez"), which would
            # otherwise never match a normally typed name.
            folded = " ".join(str(candidate).split()).casefold()
            if not folded:
                continue
            if needle == folded:
                exact.add(owner_id)
            elif needle in folded.replace("'", "").split():
                word.add(owner_id)
            elif len(needle) >= 3 and needle in folded:
                partial.add(owner_id)

    for tier in (exact, word, partial):
        if len(tier) == 1:
            return next(iter(tier))
        if len(tier) > 1:
            return None  # ambiguous at this precision; do not guess
    return None


def summary() -> dict:
    """Champions and final standings for every completed season."""
    data = build()
    if not data["seasons"]:
        return {"seasons": [], "note": "This league has no completed seasons yet"}
    seasons = []
    for year in sorted(data["years"], reverse=True):
        standings = data["years"][year]["standings"]
        seasons.append({
            "year": int(year),
            "champion": _display(data, standings[0]["owner"]) if standings else None,
            "runner_up": _display(data, standings[1]["owner"]) if len(standings) > 1 else None,
            "standings": [
                {
                    "place": row["final_standing"],
                    "manager": _display(data, row["owner"]),
                    "record": f"{row['wins']}-{row['losses']}",
                    "points_for": row["points_for"],
                }
                for row in standings
            ],
        })
    return {"seasons": seasons}


class _Tally:
    """Win/loss/tie and points, so records can be split by phase of season."""

    def __init__(self):
        self.wins = self.losses = self.ties = 0
        self.points_for = self.points_against = 0.0

    def add(self, row: dict) -> None:
        self.points_for += row["points"]
        self.points_against += row["opponent_points"]
        if row["points"] > row["opponent_points"]:
            self.wins += 1
        elif row["points"] < row["opponent_points"]:
            self.losses += 1
        else:
            self.ties += 1

    @property
    def record(self) -> str:
        base = f"{self.wins}-{self.losses}"
        return f"{base}-{self.ties}" if self.ties else base


def head_to_head(manager_a: str, manager_b: str) -> dict:
    data = build()
    a = resolve_manager(data, manager_a)
    b = resolve_manager(data, manager_b)
    if not a:
        return {"error": f"No manager matches {manager_a!r}"}
    if not b:
        return {"error": f"No manager matches {manager_b!r}"}
    if a == b:
        return {"error": "That is the same manager"}

    overall, regular = _Tally(), _Tally()
    meetings = []
    for year in sorted(data["years"]):
        for row in data["years"][year]["results"]:
            if row["owner"] != a or row["opponent"] != b:
                continue
            overall.add(row)
            if row["regular_season"]:
                regular.add(row)
            meetings.append({
                "year": int(year),
                "week": row["week"],
                "playoff": not row["regular_season"],
                "score": f"{row['points']} - {row['opponent_points']}",
            })

    if not meetings:
        return {
            "manager_a": _display(data, a),
            "manager_b": _display(data, b),
            "note": "They have never played in a completed season",
        }
    return {
        "manager_a": _display(data, a),
        "manager_b": _display(data, b),
        "record": overall.record,
        "regular_season_record": regular.record,
        "points_for": round(overall.points_for, 2),
        "points_against": round(overall.points_against, 2),
        "meetings": meetings,
        "seasons_covered": data["seasons"],
    }


def manager_record(manager: str) -> dict:
    data = build()
    owner_id = resolve_manager(data, manager)
    if not owner_id:
        return {"error": f"No manager matches {manager!r}"}

    overall, regular = _Tally(), _Tally()
    titles, finishes = [], []
    for year in sorted(data["years"]):
        for row in data["years"][year]["results"]:
            if row["owner"] != owner_id:
                continue
            overall.add(row)
            if row["regular_season"]:
                regular.add(row)
        for row in data["years"][year]["standings"]:
            if row["owner"] == owner_id:
                finishes.append({"year": int(year), "place": row["final_standing"]})
                if row["final_standing"] == 1:
                    titles.append(int(year))
    return {
        "manager": _display(data, owner_id),
        # ESPN's standings page counts regular season only. Report both so the
        # bot never contradicts what people see in the app.
        "regular_season_record": regular.record,
        "record_including_playoffs": overall.record,
        "points_for": round(overall.points_for, 2),
        "points_against": round(overall.points_against, 2),
        "championships": titles,
        "finishes": finishes,
        "seasons_covered": data["seasons"],
    }
