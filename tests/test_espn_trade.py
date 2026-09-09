import unittest
from types import SimpleNamespace
from unittest.mock import patch

from schefter import espn_trade


class EspnTradeTests(unittest.TestCase):
    def setUp(self):
        self.source = SimpleNamespace(team_id=1, team_name="Team One")
        self.target = SimpleNamespace(team_id=2, team_name="Team Two")
        self.league = SimpleNamespace(teams=[self.source, self.target], scoringPeriodId=3)
        self.proposal = {
            "id": "ab12cd34",
            "proposer_team": "Team One",
            "recipient_team": "Team Two",
            "offered_players": [{"id": 101, "name": "Player One"}],
            "requested_players": [{"id": 202, "name": "Player Two"}],
        }
        self.patches = [
            patch.object(espn_trade.config, "ESPN_TRADE_WRITE_ENABLED", True),
            patch.object(espn_trade.config, "ESPN_TRADE_AUTH_MODE", "league_manager"),
            patch.object(espn_trade.config, "ESPN_S2", "s2-cookie"),
            patch.object(espn_trade.config, "SWID", "{SWID}"),
            patch.object(espn_trade.config, "LEAGUE_ID", 999),
            patch.object(espn_trade.config, "SEASON", 2026),
            patch.object(espn_trade.espn, "get_league", return_value=self.league),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_executes_proposal_then_acceptance(self):
        with patch.object(espn_trade, "_post", side_effect=[{"id": "tx-123"}, {"ok": True}]) as post:
            result = espn_trade.execute(self.proposal)

        self.assertEqual(result, {
            "status": "submitted", "provider": "espn", "transaction_id": "tx-123"
        })
        proposal_payload = post.call_args_list[0].args[0]
        self.assertEqual(proposal_payload["type"], "TRADE_PROPOSAL")
        self.assertTrue(proposal_payload["isLeagueManager"])
        self.assertEqual(proposal_payload["items"], [
            {"playerId": 101, "type": "TRADE", "fromTeamId": 1, "toTeamId": 2},
            {"playerId": 202, "type": "TRADE", "fromTeamId": 2, "toTeamId": 1},
        ])
        accept_payload = post.call_args_list[1].args[0]
        self.assertEqual(accept_payload["type"], "TRADE_ACCEPT")
        self.assertEqual(accept_payload["teamId"], 2)
        self.assertEqual(accept_payload["relatedTransactionId"], "tx-123")

    def test_write_kill_switch_prevents_requests(self):
        with patch.object(espn_trade.config, "ESPN_TRADE_WRITE_ENABLED", False), \
             patch.object(espn_trade, "_post") as post:
            result = espn_trade.execute(self.proposal)
        self.assertEqual(result["status"], "configuration_error")
        post.assert_not_called()

    def test_accept_failure_preserves_pending_transaction_id(self):
        with patch.object(
            espn_trade, "_post",
            side_effect=[{"transaction": {"id": 456}}, espn_trade.EspnTradeError("accept failed")],
        ):
            result = espn_trade.execute(self.proposal)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["phase"], "acceptance")
        self.assertEqual(result["transaction_id"], "456")

    def test_post_uses_espn_write_endpoint_and_never_logs_cookies(self):
        response = SimpleNamespace(status_code=200, json=lambda: {"id": 12})
        credentials = espn_trade.Credentials("private-s2", "{PRIVATE-SWID}")
        with patch.object(espn_trade.requests, "post", return_value=response) as post:
            result = espn_trade._post({"type": "TRADE_ACCEPT"}, credentials)
        self.assertEqual(result, {"id": 12})
        self.assertIn("lm-api-writes.fantasy.espn.com", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["cookies"], {
            "espn_s2": "private-s2", "SWID": "{PRIVATE-SWID}"
        })


if __name__ == "__main__":
    unittest.main()
