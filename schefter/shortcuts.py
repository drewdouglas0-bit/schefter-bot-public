"""Answer stereotyped history questions from SQL, without calling the model.

A question that reaches OpenAI costs roughly 4,400 input tokens even when the
answer is one row of a table. The handful of phrasings below are common enough
and rigid enough to recognize locally, so they cost nothing.

Matching is deliberately conservative. Anything that is not an unmistakable
match returns None and goes to the model, because a wrong cheap answer is worse
than a right expensive one.
"""
import re

from . import draft, espn, history, voice

_ALL_TIME = r"(?:all[-\s]?time|ever|of all time|in league history)"

_CHAMPION_LAST = re.compile(
    r"^\s*who\s+won\s+(?:the\s+|our\s+|this\s+)?(?:league|championship|it all|chip)?\s*"
    r"(?:last\s+(?:year|season))\s*\??\s*$",
    re.IGNORECASE,
)
_CHAMPION_YEAR = re.compile(
    r"^\s*who\s+won\s+(?:the\s+|our\s+)?(?:league|championship|it all|chip)?\s*"
    r"(?:in\s+)?(?P<year>20\d{2})\s*\??\s*$",
    re.IGNORECASE,
)
# Both orderings occur naturally: "the worst 5 teams" and "the 5 worst teams".
_STANDINGS = re.compile(
    rf"^\s*(?:who\s+(?:are|is|has)\s+)?(?:the\s+)?"
    rf"(?:(?P<superlative>winningest|best|worst|losingest)\s*(?P<count>\d+)?"
    rf"|(?P<count2>\d+)\s*(?P<superlative2>winningest|best|worst|losingest))\s*"
    rf"(?:teams?|managers?|players?)?\s*"
    rf"(?:{_ALL_TIME})\s*"
    rf"(?:by\s+(?P<metric>wins|losses|record|win\s*pct|points))?\s*\??\s*$",
    re.IGNORECASE,
)
_STANDINGS_TOP_N = re.compile(
    rf"^\s*(?:who\s+(?:are|is)\s+)?(?:the\s+)?top\s+(?P<count>\d+)\s*"
    rf"(?P<superlative>winningest|best|worst|losingest)?\s*(?:teams?|managers?)?\s*"
    rf"(?:{_ALL_TIME})\s*"
    rf"(?:by\s+(?P<metric>wins|losses|record|points))?\s*\??\s*$",
    re.IGNORECASE,
)


def _ordinal_place(place: int) -> str:
    if 10 <= place % 100 <= 20:
        return f"{place}th"
    return f"{place}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(place % 10, 'th') }"


def _champion(year: int | None) -> str | None:
    summary = history.summary()
    seasons = summary.get("seasons") or []
    if not seasons:
        return None
    if year is None:
        season = seasons[0]  # summary is newest first
    else:
        season = next((s for s in seasons if s["year"] == year), None)
        if season is None:
            return None
    if not season.get("champion"):
        return None
    line = f"{season['champion']} won the {season['year']} title."
    if season.get("runner_up"):
        line += f" {season['runner_up']} was runner-up."
    return line


def _sort_for(superlative: str | None, metric: str | None) -> str:
    metric = (metric or "").replace(" ", "").casefold()
    superlative = (superlative or "").casefold()
    if metric == "losses":
        return "losses"
    if metric == "wins":
        return "wins"
    if metric == "points":
        return "points_for"
    if metric in ("winpct", "record"):
        return "worst" if superlative in ("worst", "losingest") else "win_pct"
    if superlative in ("worst", "losingest"):
        return "losses"
    return "wins"


def _standings(count: int, superlative: str | None, metric: str | None) -> str | None:
    sort_by = _sort_for(superlative, metric)
    result = history.all_time_standings(sort_by=sort_by, limit=max(1, min(count, 15)))
    rows = result.get("standings")
    if not rows:
        return None
    heading = {
        "losses": "Most losses all time",
        "wins": "Winningest all time",
        "points_for": "Most points all time",
        "win_pct": "Best win percentage all time",
        "worst": "Worst win percentage all time",
    }.get(sort_by, "All time")
    lines = [f"{heading}:"]
    lines += [f"{row['rank']}. {row['manager']} {row['record']}" for row in rows]
    return "\n".join(lines)


# Recognize common head-to-head questions. Tolerate typos and missing
# apostrophes (e.g. "wat is alphas record against ..."), and both
# "record against" and "record vs".
_HEAD_TO_HEAD = re.compile(
    r"^\s*(?:wh?at(?:'?s)?|was|whos?)?\s*(?:is|are|was|been)?\s*"
    r"(?P<a>.{2,60}?)\s*(?:'s|s')?\s+"
    r"(?:all[-\s]?time\s+|career\s+|overall\s+)?record\s+"
    r"(?:against|vs\.?|versus)\s+(?P<b>.{2,60}?)\s*\??\s*$",
    re.IGNORECASE,
)

_WHO_DRAFTED = re.compile(
    r"^\s*who\s+(?:drafted|picked|took|selected)\s+(?P<player>.{2,50}?)"
    r"(?:\s+(?:in|on)\s+(?:our|the|this)\s+league)?\s*\??\s*$",
    re.IGNORECASE,
)

_STANDINGS_NOW = re.compile(
    r"^\s*(?:wh?at(?:'?s)?\s+(?:are\s+)?)?(?:the\s+|our\s+|current\s+)*"
    r"(?:league\s+)?standings\s*\??\s*$",
    re.IGNORECASE,
)


def _candidates(name: str):
    """People drop apostrophes ("alphas record"), but a bare trailing s can
    also be part of a team name ("Example Eagles"). Try the literal form first
    and only then peel a possessive off it.
    """
    cleaned = " ".join(str(name).split()).strip()
    yield cleaned
    without_apostrophe = re.sub(r"(?:'s|s'|’s)$", "", cleaned).strip()
    if without_apostrophe != cleaned:
        yield without_apostrophe
    if cleaned.lower().endswith("s"):
        yield cleaned[:-1].strip()


def _resolve(data: dict, name: str) -> tuple[str, str] | None:
    for candidate in _candidates(name):
        if not candidate:
            continue
        owner_id = history.resolve_manager(data, candidate)
        if owner_id:
            return owner_id, candidate
    return None


def _head_to_head(raw_a: str, raw_b: str) -> str | None:
    data = history.build()
    first = _resolve(data, raw_a)
    second = _resolve(data, raw_b)
    if not first or not second or first[0] == second[0]:
        return None  # ambiguous or unknown; the model can ask for clarification
    result = history.head_to_head(first[1], second[1])
    if result.get("note"):
        return f"{result['manager_a']} and {result['manager_b']} have never played."
    if not result.get("record"):
        return None
    line = f"{result['manager_a']} is {result['record']} all time against {result['manager_b']}."
    regular = result.get("regular_season_record")
    if regular and regular != result["record"]:
        line += f" Regular season: {regular}."
    return line


def _who_drafted(player: str) -> str | None:
    result = draft.results(player=player)
    picks = result.get("picks") or []
    if not picks:
        return None  # unknown player, or not drafted; let the model handle it
    lines = [
        f"{p['team']} took {p['player']} at {p['round']}.{p['pick']:02d} "
        f"(#{p['overall']} overall) in {result['year']}."
        for p in picks[:3]
    ]
    return "\n".join(lines)


def _standings_now() -> str | None:
    try:
        league = espn.get_league()
        table = league.standings()
    except Exception:
        return None
    if not table:
        return None
    week = getattr(league, "current_week", None)
    lines = [f"Standings{f' through week {week}' if week else ''}:"]
    for rank, team in enumerate(table, start=1):
        record = f"{getattr(team, 'wins', 0)}-{getattr(team, 'losses', 0)}"
        lines.append(f"{rank}. {getattr(team, 'team_name', 'Unknown')} {record}")
    return "\n".join(lines)


def answer(question: str) -> str | None:
    """A ready reply for a recognized question, or None to let the model handle it."""
    text = " ".join(str(question).split())
    if not text:
        return None

    if _CHAMPION_LAST.match(text):
        return voice.polish(_champion(None) or "") or None

    match = _CHAMPION_YEAR.match(text)
    if match:
        return voice.polish(_champion(int(match.group("year"))) or "") or None

    for pattern in (_STANDINGS_TOP_N, _STANDINGS):
        match = pattern.match(text)
        if not match:
            continue
        groups = match.groupdict()
        count = int(groups.get("count") or groups.get("count2") or 5)
        superlative = groups.get("superlative") or groups.get("superlative2")
        reply = _standings(count, superlative, groups.get("metric"))
        return voice.polish(reply) if reply else None

    match = _HEAD_TO_HEAD.match(text)
    if match:
        reply = _head_to_head(match.group("a"), match.group("b"))
        return voice.polish(reply) if reply else None

    match = _WHO_DRAFTED.match(text)
    if match:
        reply = _who_drafted(match.group("player"))
        return voice.polish(reply) if reply else None

    if _STANDINGS_NOW.match(text):
        reply = _standings_now()
        return voice.polish(reply) if reply else None
    return None
