import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from schefter import polls


class PollTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tempdir.name) / "polls.json"
        self.sent = []
        self.patches = [
            patch.object(polls.config, "POLLS_ENABLED", True),
            patch.object(polls.config, "POLL_STATE_FILE", self.state_file),
            patch.object(polls.imessage, "send", side_effect=lambda text: self.sent.append(text)),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.tempdir.cleanup()

    def _open_scoring_poll(self):
        return polls.create("Scoring format?", ["PPR", "Half PPR", "No PPR"])

    def test_create_posts_the_poll_verbatim(self):
        result = self._open_scoring_poll()

        self.assertTrue(result["posted"])
        self.assertEqual(
            self.sent,
            ["POLL: Scoring format?\n1. PPR\n2. Half PPR\n3. No PPR\nReply with a number to vote."],
        )

    def test_numbers_and_option_text_both_vote(self):
        self._open_scoring_poll()

        self.assertEqual(polls.parse_vote("1"), 0)
        self.assertEqual(polls.parse_vote("2."), 1)
        self.assertEqual(polls.parse_vote("no ppr"), 2)
        self.assertIsNone(polls.parse_vote("4"))
        self.assertIsNone(polls.parse_vote("sounds good"))

    def test_votes_are_tallied_one_per_sender_with_replacement(self):
        self._open_scoring_poll()
        polls.record_vote("+15550000001", 0)
        polls.record_vote("+15550000002", 0)
        polls.record_vote("+15550000003", 1)
        polls.record_vote("+15550000001", 2)  # changed their mind

        message = polls.results()["message"]
        self.assertIn("1. PPR: 1", message)
        self.assertIn("2. Half PPR: 1", message)
        self.assertIn("3. No PPR: 1", message)
        self.assertIn("3 votes.", message)

    def test_close_reports_the_winner_and_stops_voting(self):
        self._open_scoring_poll()
        polls.record_vote("+15550000001", 0)
        polls.record_vote("+15550000002", 0)
        polls.record_vote("+15550000003", 1)

        message = polls.close()["message"]
        self.assertIn("POLL RESULTS", message)
        self.assertIn("PPR wins.", message)
        self.assertIsNone(polls.parse_vote("1"))

    def test_tie_is_reported_as_a_tie(self):
        self._open_scoring_poll()
        polls.record_vote("+15550000001", 0)
        polls.record_vote("+15550000002", 1)

        self.assertIn("Tied: PPR, Half PPR.", polls.close()["message"])

    def test_second_poll_is_refused_while_one_is_open(self):
        self._open_scoring_poll()
        self.sent.clear()

        result = polls.create("Trade deadline?", ["Week 10", "Week 12"])

        self.assertIn("already open", result["error"])
        self.assertEqual(self.sent, [])

    def test_poll_is_not_left_open_when_posting_fails(self):
        with patch.object(polls.imessage, "send", side_effect=RuntimeError("boom")):
            result = polls.create("Scoring format?", ["PPR", "No PPR"])

        self.assertIn("could not be posted", result["error"])
        self.assertIsNone(polls.parse_vote("1"))
        # The failed poll must not block the next one.
        self.assertTrue(self._open_scoring_poll()["posted"])

    def test_option_validation(self):
        self.assertIn("2 to 9 options", polls.create("One?", ["Only"])["error"])
        self.assertIn("unique", polls.create("Dupes?", ["PPR", "ppr"])["error"])
        self.assertEqual(self.sent, [])

    def test_disabled_polls_do_not_post_or_consume_replies(self):
        self._open_scoring_poll()
        with patch.object(polls.config, "POLLS_ENABLED", False):
            self.assertIsNone(polls.parse_vote("1"))
            self.assertIn("disabled", polls.create("Another?", ["A", "B"])["error"])


if __name__ == "__main__":
    unittest.main()
