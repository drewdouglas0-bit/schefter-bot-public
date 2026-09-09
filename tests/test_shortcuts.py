import unittest
from unittest.mock import patch

from schefter import shortcuts


SUMMARY = {
    "seasons": [
        {"year": 2025, "champion": "Ann Alpha (Alpha Squad)",
         "runner_up": "Bo Beta (Beta Crew)", "standings": []},
        {"year": 2024, "champion": "Bo Beta (Beta Crew)",
         "runner_up": "Ann Alpha (Alpha Squad)", "standings": []},
    ]
}

STANDINGS = {
    "sorted_by": "wins",
    "seasons_covered": [2024, 2025],
    "standings": [
        {"rank": 1, "manager": "Ann Alpha (Alpha Squad)", "record": "20-8"},
        {"rank": 2, "manager": "Bo Beta (Beta Crew)", "record": "15-13"},
        {"rank": 3, "manager": "Cy Gamma (Gamma Gang)", "record": "9-19"},
    ],
}


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake_standings(sort_by="wins", limit=None):
            self.calls.append(sort_by)
            return STANDINGS

        self.patches = [
            patch.object(shortcuts.history, "summary", return_value=SUMMARY),
            patch.object(shortcuts.history, "all_time_standings", side_effect=fake_standings),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()

    def test_last_years_champion(self):
        for question in ("who won last year", "who won the league last year?"):
            self.assertIn("Ann Alpha", shortcuts.answer(question), question)

    def test_champion_for_a_named_year(self):
        self.assertIn("Bo Beta", shortcuts.answer("who won in 2024"))

    def test_unknown_year_falls_through_to_the_model(self):
        self.assertIsNone(shortcuts.answer("who won in 2019"))

    def test_both_word_orders_match(self):
        for question in ("the worst 5 teams all time", "the 5 worst teams all time"):
            self.assertIsNotNone(shortcuts.answer(question), question)

    def test_winningest_sorts_by_wins_and_worst_by_losses(self):
        shortcuts.answer("top 5 winningest teams all time")
        shortcuts.answer("5 worst teams all time")
        self.assertEqual(self.calls, ["wins", "losses"])

    def test_explicit_metric_wins_over_the_superlative(self):
        self.calls.clear()
        shortcuts.answer("the best 5 teams all time by points")
        self.assertEqual(self.calls, ["points_for"])

    def test_open_ended_questions_are_left_to_the_model(self):
        for question in (
            "who should i start this week",
            "thoughts on my roster",
            "who won the super bowl",
            "who won our matchup",
            "is bijan playing",
        ):
            self.assertIsNone(shortcuts.answer(question), question)

    def test_head_to_head_phrasings_with_synthetic_managers(self):
        """Synthetic phrasings preserve typo and possessive regression coverage."""
        data = {"managers": {
            "{A}": {"name": "Ann Alpha", "teams": {"2025": "Alpha Squad"}},
            "{B}": {"name": "Bo Beta", "teams": {"2025": "Beta Crew"}},
        }}
        h2h = {"manager_a": "Ann Alpha (Alpha Squad)", "manager_b": "Bo Beta (Beta Crew)",
               "record": "2-3", "regular_season_record": "2-2", "meetings": [1]}
        with patch.object(shortcuts.history, "build", return_value=data), \
             patch.object(shortcuts.history, "resolve_manager",
                          side_effect=lambda d, n: {"ann alpha": "{A}", "alpha": "{A}",
                                                    "bo beta": "{B}", "beta": "{B}"}.get(n.casefold())), \
             patch.object(shortcuts.history, "head_to_head", return_value=h2h):
            for question in (
                "what is bo beta's all time record against ann alpha",
                "wat is Alphas all time record against beta",       # typo, no apostrophe
                "what is alpha record against beta",                # no possessive at all
                "whats alphas career record vs beta",
            ):
                self.assertIsNotNone(shortcuts.answer(question), question)

    def test_unknown_manager_falls_through_instead_of_guessing(self):
        with patch.object(shortcuts.history, "build", return_value={"managers": {}}), \
             patch.object(shortcuts.history, "resolve_manager", return_value=None):
            self.assertIsNone(shortcuts.answer("what is nobody's record against no one"))

    def test_who_drafted_falls_through_when_the_player_is_not_found(self):
        with patch.object(shortcuts.draft, "results", return_value={"picks": [], "year": 2026}):
            self.assertIsNone(shortcuts.answer("who drafted nobody real"))

    def test_who_drafted_reports_the_pick(self):
        picks = {"year": 2026, "picks": [
            {"round": 1, "pick": 2, "overall": 2, "player": "Bijan Robinson",
             "team": "Alpha Squad", "manager": "Ann Alpha"}]}
        with patch.object(shortcuts.draft, "results", return_value=picks):
            reply = shortcuts.answer("who drafted bijan robinson")
        self.assertIn("Bijan Robinson", reply)
        self.assertIn("1.02", reply)

    def test_no_seasons_falls_through_rather_than_answering_emptily(self):
        with patch.object(shortcuts.history, "summary", return_value={"seasons": []}):
            self.assertIsNone(shortcuts.answer("who won last year"))


if __name__ == "__main__":
    unittest.main()
