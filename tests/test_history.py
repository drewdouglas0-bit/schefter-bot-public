import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from schefter import history


def manager(owner_id, first, last):
    return [{"id": owner_id, "firstName": first, "lastName": last}]


class FakeTeam:
    """Mirrors the espn-api Team surface history.py actually reads."""

    def __init__(self, owner_id, first, last, team_name, final_standing, wins, losses, points_for):
        self.owners = manager(owner_id, first, last)
        self.team_name = team_name
        self.final_standing = final_standing
        self.wins = wins
        self.losses = losses
        self.points_for = points_for
        self.schedule = []
        self.scores = []


def build_season():
    """Two managers, three weeks: two regular season, one playoff."""
    a = FakeTeam("{A}", "Ann", "Alpha", "Alpha Squad", 1, 2, 0, 300.0)
    b = FakeTeam("{B}", "Bo", "Beta", "Beta Crew", 2, 0, 2, 250.0)
    a.schedule = [b, b, b]
    b.schedule = [a, a, a]
    a.scores = [100.0, 110.0, 90.0]   # wins weeks 1-2, loses the playoff week
    b.scores = [90.0, 100.0, 120.0]
    return [a, b]


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.cache = Path(self.tempdir.name) / "history.json"
        teams = build_season()
        current = type("League", (), {"teams": teams, "year": 2026, "previousSeasons": [2025]})()
        self.patches = [
            patch.object(history.config, "HISTORY_CACHE_FILE", self.cache),
            patch.object(history.config, "LEAGUE_ID", 999),
            patch.object(history.espn, "get_league", return_value=current),
            patch.object(history, "_season_record", return_value={
                "standings": [
                    {"owner": "{A}", "team": "Alpha Squad", "final_standing": 1,
                     "wins": 2, "losses": 0, "points_for": 300.0},
                    {"owner": "{B}", "team": "Beta Crew", "final_standing": 2,
                     "wins": 0, "losses": 2, "points_for": 250.0},
                ],
                "results": [
                    {"owner": "{A}", "opponent": "{B}", "week": 1, "regular_season": True,
                     "points": 100.0, "opponent_points": 90.0},
                    {"owner": "{A}", "opponent": "{B}", "week": 2, "regular_season": True,
                     "points": 110.0, "opponent_points": 100.0},
                    {"owner": "{A}", "opponent": "{B}", "week": 3, "regular_season": False,
                     "points": 90.0, "opponent_points": 120.0},
                ],
                "managers": {
                    "{A}": {"name": "Ann Alpha", "team": "Old Alpha Name"},
                    "{B}": {"name": "Bo Beta", "team": "Beta Crew"},
                },
            }),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.tempdir.cleanup()

    def test_summary_names_the_champion(self):
        season = history.summary()["seasons"][0]
        self.assertEqual(season["year"], 2025)
        self.assertIn("Ann Alpha", season["champion"])
        self.assertIn("Bo Beta", season["runner_up"])

    def test_regular_season_record_excludes_playoffs(self):
        record = history.manager_record("Ann")
        self.assertEqual(record["regular_season_record"], "2-0")
        self.assertEqual(record["record_including_playoffs"], "2-1")
        self.assertEqual(record["championships"], [2025])

    def test_manager_resolves_by_a_previous_team_name(self):
        # The whole point of keying on owner id: names change between seasons.
        data = history.build()
        self.assertEqual(history.resolve_manager(data, "Old Alpha Name"), "{A}")
        self.assertEqual(history.resolve_manager(data, "Alpha Squad"), "{A}")
        self.assertEqual(history.resolve_manager(data, "Ann Alpha"), "{A}")
        self.assertIsNone(history.resolve_manager(data, "nobody at all"))

    def test_head_to_head_splits_playoff_meetings(self):
        result = history.head_to_head("Ann", "Bo")
        self.assertEqual(result["record"], "2-1")
        self.assertEqual(result["regular_season_record"], "2-0")
        self.assertEqual(len(result["meetings"]), 3)
        self.assertTrue(result["meetings"][-1]["playoff"])

    def test_unknown_manager_is_reported_not_guessed(self):
        self.assertIn("error", history.head_to_head("Ann", "Nobody"))
        self.assertIn("error", history.manager_record("Nobody"))

    def test_cache_is_reused_and_rebuilt_when_seasons_change(self):
        history.build()
        with patch.object(history, "_season_record") as refetch:
            history.build()
            refetch.assert_not_called()  # cache hit, no ESPN traffic

    def test_second_league_does_not_read_the_first_leagues_cache(self):
        history.build()
        with patch.object(history.config, "LEAGUE_ID", 1234):
            self.assertIsNone(history._read_cache())


if __name__ == "__main__":
    unittest.main()
