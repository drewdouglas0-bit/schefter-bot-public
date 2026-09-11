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
            team_name="Team One", owner="Alex", team_id=1,
            owners=[{"id": "{A}", "firstName": "Alex", "lastName": "Carter"}],
            roster=[player(1, "CeeDee Lamb")],
        )
        self.team_two = SimpleNamespace(
            team_name="Team Two", owner="Taylor", team_id=2,
            owners=[{"id": "{B}", "firstName": "Taylor", "lastName": "Reed"}],
            roster=[player(2, "Ja'Marr Chase")],
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
        self.assertEqual(
            [(p["id"], p["name"]) for p in proposal["offered_players"]],
            [(1, "CeeDee Lamb")],
        )
        self.assertNotIn("recipient_sender", proposal)
        self.assertTrue(self.state_file.exists())

    def test_confirmation_states_the_terms_and_nothing_else(self):
        """The chat gets fixed wording, not the model's take on the trade."""
        self.team_one.roster = [
            SimpleNamespace(playerId=1, name="Puka Nacua", position="WR", proTeam="LAR")
        ]
        self.team_two.roster = [
            SimpleNamespace(playerId=2, name="Ja'Marr Chase", position="WR", proTeam="CIN")
        ]
        message = trades.create(
            "+15550000001", "Team Two", ["Puka Nacua"], ["Ja'Marr Chase"]
        )["message"]
        proposal_id = message.split()[1]
        self.assertEqual(
            message,
            f"Trade {proposal_id} proposed. Team One sends WR Puka Nacua (LAR). "
            f"Team Two sends WR Ja'Marr Chase (CIN). Awaiting a reply from Team Two.",
        )

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

    def test_target_team_is_derived_from_who_rosters_the_wanted_player(self):
        """"offer Vidal for Brock Bowers" names no team, so the model puts the
        player in the team slot. A player sits on one roster; use that."""
        result = trades.create(
            "+15550000001", "Ja'Marr Chase", ["CeeDee Lamb"], ["Ja'Marr Chase"]
        )
        self.assertNotIn("error", result)
        self.assertEqual(result["proposal"]["recipient_team"], "Team Two")

    def test_players_match_on_surname(self):
        result = trades.create("+15550000001", "Team Two", ["Lamb"], ["Chase"])
        self.assertNotIn("error", result)
        self.assertEqual(result["proposal"]["offered_players"][0]["name"], "CeeDee Lamb")
        self.assertEqual(result["proposal"]["requested_players"][0]["name"], "Ja'Marr Chase")

    def test_players_match_on_the_short_forms_people_type(self):
        self.team_two.roster = [player(2, "Christian McCaffrey"), player(4, "Marvin Harrison Jr.")]
        roster = self.team_two.roster
        self.assertEqual(trades._match_player(roster, "cmc").name, "Christian McCaffrey")
        self.assertEqual(trades._match_player(roster, "CMC").name, "Christian McCaffrey")
        self.assertEqual(trades._match_player(roster, "mhj").name, "Marvin Harrison Jr.")

    def test_a_short_form_shared_by_two_players_is_refused(self):
        self.team_two.roster = [player(2, "Chris Carson"), player(4, "Cooper Cupp")]
        # both reduce to "cc", so neither is a safe guess
        self.assertIsNone(trades._match_player(self.team_two.roster, "cc"))

    def test_player_names_survive_a_typo(self):
        self.team_two.roster = [player(2, "Christian McCaffrey")]
        result = trades.create("+15550000001", "Team Two", ["Lamb"], ["mcaffery"])
        self.assertNotIn("error", result)
        self.assertEqual(
            result["proposal"]["requested_players"][0]["name"], "Christian McCaffrey"
        )

    def test_a_recipient_named_inline_is_not_treated_as_a_player(self):
        """"offer taylor lamb for chase" puts the recipient in the player list."""
        result = trades.create("+15550000001", "", ["Taylor", "CeeDee Lamb"], ["Ja'Marr Chase"])
        self.assertNotIn("error", result)
        self.assertEqual(
            [p["name"] for p in result["proposal"]["offered_players"]], ["CeeDee Lamb"]
        )
        self.assertEqual(result["proposal"]["recipient_team"], "Team Two")

    def test_an_ambiguous_player_name_is_refused(self):
        self.team_two.roster.append(player(3, "Justin Chase"))
        result = trades.create("+15550000001", "Team Two", ["CeeDee Lamb"], ["Chase"])
        self.assertIn("error", result)

    def test_a_mapping_by_owner_name_survives_a_team_rename(self):
        """Team names change between and during seasons; people do not."""
        with patch.object(trades.config, "TRADE_MANAGERS", {
            "+15550000001": "Alex Carter", "+15550000002": "Taylor Reed"
        }):
            self.team_one.team_name = "Renamed Overnight"
            result = trades.create(
                "+15550000001", "Taylor Reed", ["CeeDee Lamb"], ["Ja'Marr Chase"]
            )
        self.assertNotIn("error", result)
        self.assertEqual(result["proposal"]["proposer_team"], "Renamed Overnight")
        self.assertEqual(result["proposal"]["recipient_team"], "Team Two")

    def test_team_names_match_despite_stray_espn_whitespace(self):
        self.team_one.team_name = "Team One "  # ESPN really does store these
        self.assertIs(trades._find_team("Team One"), self.team_one)
        self.assertIs(trades._find_team("  team   one  "), self.team_one)

    def test_an_ambiguous_surname_is_refused_rather_than_guessed(self):
        self.team_two.owners = [{"id": "{B}", "firstName": "Bob", "lastName": "Carter"}]
        with self.assertRaises(ValueError):
            trades._find_team("Carter")
        self.assertIs(trades._find_team("Alex Carter"), self.team_one)

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
