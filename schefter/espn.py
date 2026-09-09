"""Thin wrapper around espn-api's league activity feed."""
from espn_api.football import League

from . import config

_league = None


def get_league() -> League:
    global _league
    if config.LEAGUE_ID is None:
        raise RuntimeError("ESPN_LEAGUE_ID is not set in .env")
    if _league is None:
        _league = League(
            league_id=config.LEAGUE_ID,
            year=config.SEASON,
            espn_s2=config.ESPN_S2,
            swid=config.SWID,
        )
    return _league


def recent_activity(size: int | None = None):
    """Activities oldest-first, so the chat reads in chronological order."""
    league = get_league()
    activities = league.recent_activity(size=size or config.FETCH_SIZE)
    return sorted(activities, key=lambda a: a.date)
