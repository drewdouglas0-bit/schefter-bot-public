"""SQLite store for completed-season league data.

History used to be a JSON blob the model had to aggregate in its own context.
Asking for "the winningest teams" meant sending every standings row and hoping
it summed four seasons correctly, which it did inconsistently. Aggregates
belong in SQL, where they are exact and the answer is a handful of rows.

Managers are keyed by ESPN owner id throughout. Team names change between
seasons, so they are display data only, never an identity.
"""
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS managers (
    owner_id TEXT PRIMARY KEY,
    name     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS team_seasons (
    year           INTEGER NOT NULL,
    owner_id       TEXT    NOT NULL,
    team_name      TEXT    NOT NULL,
    final_standing INTEGER,
    wins           INTEGER NOT NULL DEFAULT 0,
    losses         INTEGER NOT NULL DEFAULT 0,
    points_for     REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (year, owner_id)
);
CREATE TABLE IF NOT EXISTS results (
    year            INTEGER NOT NULL,
    week            INTEGER NOT NULL,
    owner_id        TEXT    NOT NULL,
    opponent_id     TEXT    NOT NULL,
    regular_season  INTEGER NOT NULL,
    points          REAL    NOT NULL,
    opponent_points REAL    NOT NULL,
    PRIMARY KEY (year, week, owner_id)
);
CREATE INDEX IF NOT EXISTS results_owner ON results (owner_id);
CREATE INDEX IF NOT EXISTS results_pair  ON results (owner_id, opponent_id);
"""


@contextmanager
def connect():
    connection = sqlite3.connect(config.HISTORY_DB_FILE)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(_SCHEMA)
        yield connection
        connection.commit()
    finally:
        connection.close()


def _meta(connection, key: str) -> str | None:
    row = connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def stored_seasons() -> list[int]:
    with connect() as connection:
        if _meta(connection, "schema_version") != str(SCHEMA_VERSION):
            return []
        if _meta(connection, "league_id") != str(config.LEAGUE_ID):
            return []  # a different league's database; treat as empty
        rows = connection.execute("SELECT year FROM team_seasons GROUP BY year ORDER BY year")
        return [row["year"] for row in rows]


def replace_seasons(seasons: dict, managers: dict) -> None:
    """Write a full rebuild. Seasons are immutable, so this is all-or-nothing."""
    with connect() as connection:
        connection.execute("DELETE FROM results")
        connection.execute("DELETE FROM team_seasons")
        connection.execute("DELETE FROM managers")
        connection.executemany(
            "INSERT INTO managers (owner_id, name) VALUES (?, ?)",
            [(owner_id, info.get("name", "Unknown manager")) for owner_id, info in managers.items()],
        )
        for year, season in seasons.items():
            connection.executemany(
                "INSERT INTO team_seasons "
                "(year, owner_id, team_name, final_standing, wins, losses, points_for) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (int(year), row["owner"], row["team"], row["final_standing"],
                     row["wins"], row["losses"], row["points_for"])
                    for row in season["standings"]
                ],
            )
            connection.executemany(
                "INSERT OR REPLACE INTO results "
                "(year, week, owner_id, opponent_id, regular_season, points, opponent_points) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (int(year), row["week"], row["owner"], row["opponent"],
                     1 if row["regular_season"] else 0, row["points"], row["opponent_points"])
                    for row in season["results"]
                ],
            )
        connection.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        connection.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('league_id', ?)",
            (str(config.LEAGUE_ID),),
        )


# Named metrics, so "winningest" and "worst" mean one defined thing rather than
# whatever the model decides to compute that time.
SORTS = {
    "wins": "wins DESC, win_pct DESC",
    "losses": "losses DESC",
    "win_pct": "win_pct DESC, wins DESC",
    "points_for": "points_for DESC",
    "championships": "championships DESC, win_pct DESC",
    "average_finish": "average_finish ASC",
    "worst": "win_pct ASC, wins ASC",
}


def all_time_standings(sort_by: str = "wins", limit: int | None = None) -> list[dict]:
    order = SORTS.get(sort_by, SORTS["wins"])
    query = f"""
        SELECT
            m.owner_id,
            m.name AS manager,
            (SELECT team_name FROM team_seasons t2
              WHERE t2.owner_id = m.owner_id ORDER BY year DESC LIMIT 1) AS team,
            COUNT(r.week)                                         AS games,
            SUM(r.points > r.opponent_points)                     AS wins,
            SUM(r.points < r.opponent_points)                     AS losses,
            SUM(r.points = r.opponent_points)                     AS ties,
            ROUND(SUM(r.points), 2)                               AS points_for,
            ROUND(SUM(r.points > r.opponent_points) * 1.0
                  / NULLIF(COUNT(r.week), 0), 3)                  AS win_pct,
            (SELECT COUNT(*) FROM team_seasons t3
              WHERE t3.owner_id = m.owner_id AND t3.final_standing = 1) AS championships,
            (SELECT ROUND(AVG(final_standing), 2) FROM team_seasons t4
              WHERE t4.owner_id = m.owner_id AND t4.final_standing > 0) AS average_finish,
            (SELECT COUNT(*) FROM team_seasons t5
              WHERE t5.owner_id = m.owner_id)                     AS seasons
        FROM managers m
        JOIN results r ON r.owner_id = m.owner_id
        GROUP BY m.owner_id
        HAVING games > 0
        ORDER BY {order}
    """
    with connect() as connection:
        rows = [dict(row) for row in connection.execute(query)]
    return rows[:limit] if limit else rows


def extremes(kind: str = "blowout", limit: int = 5) -> list[dict]:
    """Superlatives that are awkward to compute from raw standings."""
    selects = {
        "blowout": ("ROUND(points - opponent_points, 2) AS margin",
                    "points > opponent_points", "margin DESC"),
        "highest_score": ("ROUND(points, 2) AS margin", "1=1", "points DESC"),
        "lowest_score": ("ROUND(points, 2) AS margin", "1=1", "points ASC"),
        "closest": ("ROUND(ABS(points - opponent_points), 2) AS margin",
                    "points <> opponent_points", "margin ASC"),
    }
    extra, where, order = selects.get(kind, selects["blowout"])
    query = f"""
        SELECT r.year, r.week, r.regular_season,
               w.name AS manager, l.name AS opponent,
               ROUND(r.points, 2) AS points,
               ROUND(r.opponent_points, 2) AS opponent_points,
               {extra}
        FROM results r
        JOIN managers w ON w.owner_id = r.owner_id
        JOIN managers l ON l.owner_id = r.opponent_id
        WHERE {where}
        ORDER BY {order}
        LIMIT ?
    """
    with connect() as connection:
        return [dict(row) for row in connection.execute(query, (limit,))]
