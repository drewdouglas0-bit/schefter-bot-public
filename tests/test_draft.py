import unittest
from types import SimpleNamespace
from unittest.mock import patch

from schefter import draft


def team(name, first, last):
    return SimpleNamespace(
        team_name=name,
        owners=[{"id": "{X}", "firstName": first, "lastName": last}],
    )


def pick(round_num, round_pick, player, team_obj):
    return SimpleNamespace(
        round_num=round_num,
        round_pick=round_pick,
        playerName=player,
        playerId=1,
        team=team_obj,
    )


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.alpha = team("Alpha Squad", "Ann", "Alpha")
        self.beta = team("Beta Crew", "Bo", "Beta")
        picks = [
            pick(1, 1, "Bijan Robinson", self.alpha),
            pick(1, 2, "Ja'Marr Chase", self.beta),
            pick(2, 1, "Puka Nacua", self.beta),
            pick(2, 2, "Jahmyr Gibbs", self.alpha),
        ]
        self.league = SimpleNamespace(
            year=2026,
            draft=picks,
            teams=[self.alpha, self.beta],
            refresh_draft=lambda: None,  # real League objects always expose this
        )
        self.patch = patch.object(draft.espn, "get_league", return_value=self.league)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_round_filter(self):
        result = draft.results(round_num=1)
        self.assertEqual([p["player"] for p in result["picks"]],
                         ["Bijan Robinson", "Ja'Marr Chase"])

    def test_player_lookup_reports_where_they_went(self):
        result = draft.results(player="bijan")
        self.assertEqual(len(result["picks"]), 1)
        self.assertEqual(result["picks"][0]["team"], "Alpha Squad")
        self.assertEqual(result["picks"][0]["overall"], 1)

    def test_team_matches_by_name_or_manager(self):
        for query in ("Alpha Squad", "Ann", "Ann Alpha"):
            result = draft.results(team=query)
            self.assertEqual(
                [p["player"] for p in result["picks"]],
                ["Bijan Robinson", "Jahmyr Gibbs"],
                query,
            )

    def test_overall_pick_number_accounts_for_league_size(self):
        result = draft.results(round_num=2)
        self.assertEqual([p["overall"] for p in result["picks"]], [3, 4])

    def test_duplicate_picks_from_a_double_refresh_are_ignored(self):
        # espn-api's refresh_draft() appends rather than replaces.
        self.league.draft = self.league.draft + list(self.league.draft)
        result = draft.results(team="Alpha Squad")
        self.assertEqual([p["player"] for p in result["picks"]],
                         ["Bijan Robinson", "Jahmyr Gibbs"])

    def test_no_match_explains_what_was_searched(self):
        result = draft.results(player="Nobody Real")
        self.assertEqual(result["picks"], [])
        self.assertIn("Nobody Real", result["note"])

    def test_undrafted_season_is_reported_plainly(self):
        self.league.draft = []
        self.assertIn("no draft results", draft.results()["note"])


if __name__ == "__main__":
    unittest.main()
