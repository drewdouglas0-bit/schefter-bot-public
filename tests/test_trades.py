import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from schefter import trades


def player(player_id, name):
    return SimpleNamespace(playerId=player_id, name=name)


class TradeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tempdir.name) / "trades.json"
        self.team_one = SimpleNamespace(
            team_name="Team One", owner="Alex", roster=[player(1, "CeeDee Lamb")]
        )
        self.team_two = SimpleNamespace(
            team_name="Team Two", owner="Taylor", roster=[player(2, "Ja'Marr Chase")]
        )
        self.patches = [
            patch.object(trades.config, "TRADE_ENABLED", True),
            patch.object(trades.config, "TRADE_STATE_FILE", self.state_file),
            patch.object(trades.config, "TRADE_MANAGERS", {
                "+15550000001": "Team One", "+15550000002": "Team Two"
            }),
            patch.object(trades.config, "TRADE_EXECUTION_WEBHOOK_URL", ""),
            patch.object(trades.config, "TRADE_EXECUTION_PROVIDER", "none"),
            patch.object(trades.espn, "get_league", return_value=SimpleNamespace(
                teams=[self.team_one, self.team_two]
            )),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tempdir.cleanup()

    def test_create_validates_rosters_and_hides_addresses(self):
        result = trades.create(
            "+15550000001", "Team Two", ["CeeDee Lamb"], ["Ja'Marr Chase"]
        )
        proposal = result["proposal"]
        self.assertEqual(proposal["status"], "pending")
        self.assertEqual(proposal["offered_players"], [{"id": 1, "name": "CeeDee Lamb"}])
        self.assertNotIn("recipient_sender", proposal)
        self.assertTrue(self.state_file.exists())

    def test_only_recipient_can_accept_and_acceptance_is_durable(self):
        proposal_id = trades.create(
            "+15550000001", "Team Two", ["CeeDee Lamb"], ["Ja'Marr Chase"]
        )["proposal"]["id"]
        denied = trades.respond("+15550000001", "accept", proposal_id)
        self.assertIn("error", denied)

        accepted = trades.respond("+15550000002", "accept", proposal_id)["proposal"]
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(accepted["execution"]["status"], "approval_recorded")
        stored = json.loads(self.state_file.read_text())["proposals"][0]
        self.assertEqual(stored["status"], "accepted")

    def test_bare_yes_requires_exactly_one_recipient_offer(self):
        trades.create("+15550000001", "Team Two", ["CeeDee Lamb"], ["Ja'Marr Chase"])
        with patch.object(trades.config, "TRADE_ALLOW_BARE_RESPONSES", True):
            reply = trades.bare_response("+15550000002", "Yes")
        self.assertIn("accepted", reply)
        self.assertIn("provider submission is not configured", reply)

    def test_rejects_player_not_owned_by_manager(self):
        result = trades.create(
            "+15550000001", "Team Two", ["Ja'Marr Chase"], ["CeeDee Lamb"]
        )
        self.assertIn("error", result)

    def test_execution_hook_is_signed_and_idempotent(self):
        proposal_id = trades.create(
            "+15550000001", "Team Two", ["CeeDee Lamb"], ["Ja'Marr Chase"]
        )["proposal"]["id"]

        class Response:
            status = 202
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None

        with patch.object(trades.config, "TRADE_EXECUTION_WEBHOOK_URL", "https://adapter.example/trade"), \
             patch.object(trades.config, "TRADE_EXECUTION_PROVIDER", "webhook"), \
             patch.object(trades.config, "TRADE_EXECUTION_SECRET", "test-secret"), \
             patch.object(trades.urllib.request, "urlopen", return_value=Response()) as send:
            result = trades.respond("+15550000002", "accept", proposal_id)["proposal"]

        self.assertEqual(result["execution"]["status"], "submitted")
        request = send.call_args.args[0]
        self.assertEqual(request.headers["X-schefter-event-id"], proposal_id)
        self.assertTrue(request.headers["X-schefter-signature"].startswith("sha256="))


if __name__ == "__main__":
    unittest.main()
