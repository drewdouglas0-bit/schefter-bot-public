"""Exercise the real trade path with fictional rosters and NO network or .env.

The generated chat is a staged demo, not a recording of a live league or LLM.
Only the acceptance reply is verbatim bot output; the offer summary is scripted.
"""
import argparse
import json
import random
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--bot-root", type=Path, default=ROOT)
args = parser.parse_args()
sys.path.insert(0, str(args.bot_root.resolve()))

# Inject an entirely fictional configuration BEFORE importing any bot modules.
# Neither the real .env nor an existing trade-state file can be read.
config = NS(
    TZ=ZoneInfo("America/New_York"), TRADE_ENABLED=True,
    TRADE_ALLOW_BARE_RESPONSES=True, TRADE_EXECUTION_PROVIDER="espn",
    TRADE_MANAGERS={"maya@example.com": "Sunday Scaries", "jake@example.com": "Jake's Rebuild"},
    ESPN_TRADE_WRITE_ENABLED=True, ESPN_TRADE_AUTH_MODE="league_manager",
    ESPN_S2="fictional-demo-cookie", SWID="{FICTIONAL-DEMO-SWID}",
    ESPN_TRADE_CREDENTIALS_FILE=None, ESPN_TRADE_TIMEOUT=15,
    LEAGUE_ID=999, SEASON=2026,
)
sys.modules["schefter.config"] = config
from schefter import espn, espn_trade, formatter, trades  # noqa: E402

jake = NS(team_id=1, team_name="Jake's Rebuild", roster=[
    NS(playerId=202, name="Jaylen Warren", position="RB", proTeam="PIT")])
maya = NS(team_id=2, team_name="Sunday Scaries", roster=[
    NS(playerId=101, name="Chris Olave", position="WR", proTeam="NO")])
league = NS(teams=[jake, maya], scoringPeriodId=1, current_week=1)
random.seed(5)
waiver = formatter.format_activity(NS(actions=[(jake, "WAIVER ADDED", jake.roster[0], 31)]))
transaction_id = "demo-transaction-001"
proposal_id = "7a31c908"
requests_seen = []


def fake_post(url, **kwargs):
    assert url == f"{espn_trade.WRITE_ROOT}/seasons/2026/segments/0/leagues/999/transactions/"
    payload = json.loads(kwargs["data"])
    requests_seen.append(payload)
    assert kwargs["cookies"] == {"espn_s2": config.ESPN_S2, "SWID": config.SWID}
    if len(requests_seen) == 1:
        assert payload["type"] == "TRADE_PROPOSAL"
        assert payload["teamId"] == 2
        assert payload["items"] == [
            {"playerId": 101, "type": "TRADE", "fromTeamId": 2, "toTeamId": 1},
            {"playerId": 202, "type": "TRADE", "fromTeamId": 1, "toTeamId": 2},
        ]
        return NS(status_code=200, json=lambda: {"id": transaction_id})
    assert len(requests_seen) == 2
    assert payload["type"] == "TRADE_ACCEPT"
    assert payload["teamId"] == 1
    assert payload["relatedTransactionId"] == transaction_id
    return NS(status_code=200, json=lambda: {"ok": True})


with TemporaryDirectory(prefix="schefter-trade-demo-") as state_dir, \
        patch("requests.sessions.Session.request", side_effect=AssertionError("Network disabled in demo")), \
        patch("urllib.request.urlopen", side_effect=AssertionError("Network disabled in demo")), \
        patch.object(espn, "get_league", return_value=league), \
        patch.object(espn_trade.requests, "post", side_effect=fake_post), \
        patch.object(trades, "_now", return_value="2026-09-09T09:41:00-04:00"), \
        patch.object(trades.uuid, "uuid4", return_value=NS(hex=proposal_id + "0" * 24)):
    config.TRADE_STATE_FILE = Path(state_dir) / "trades.json"
    proposal = trades.create("maya@example.com", "Jake's Rebuild", ["Chris Olave"], ["Jaylen Warren"])["proposal"]
    assert proposal["status"] == "pending"
    assert proposal["execution"]["status"] == "waiting_for_acceptance"
    assert len(trades.pending("jake@example.com")["proposals"]) == 1
    assert not requests_seen, "No ESPN submission before recipient consents"
    assert trades.bare_response("maya@example.com", "Yes") is None, "Proposer cannot accept for recipient"
    assert trades.bare_response("spectator@example.com", "Yes") is None, "Bystander cannot accept"
    assert not requests_seen
    acceptance = trades.bare_response("jake@example.com", "Yes")
    assert acceptance == f"Trade {proposal_id} accepted. The provider submission was sent."
    stored = json.loads(config.TRADE_STATE_FILE.read_text())["proposals"][0]
    assert stored["status"] == "accepted"
    assert stored["execution"] == {"status": "submitted", "provider": "espn", "transaction_id": transaction_id}
    assert trades.pending("jake@example.com") == {"proposals": []}
    assert trades.bare_response("jake@example.com", "Yes") is None, "Duplicate acceptance must not resubmit"
    assert len(requests_seen) == 2


def message(at, who, lines):
    return {"at": at, "who": who, "lines": lines}


messages = [
    message(9, "Jake", ["waivers are gonna be quiet"]),
    message(42, "Schefter Bot", ["Waiver claim: Jake's Rebuild gets", "RB Jaylen Warren (PIT) for $31", "of FAAB."]),
    message(130, "Drew", ["$31????"]),
    message(170, "Maya", ["Schefter, offer Jake's Rebuild", "Chris Olave for Jaylen Warren."]),
    message(258, "Schefter Bot", [f"Trade {proposal_id}:", "Maya sends Chris Olave.", "Jake sends Jaylen Warren.", "Jake, reply Yes to accept."]),
    message(405, "Jake", ["Yes"]),
    message(441, "Schefter Bot", [f"Trade {proposal_id} accepted. The", "provider submission was sent."]),
    message(555, "Drew", ["he spent $31 just to trade him"]),
    message(638, "Jake", ["value investing"]),
]
assert " ".join(messages[1]["lines"]) == waiver
assert " ".join(messages[6]["lines"]) == acceptance
assert proposal["offered_players"][0]["name"] in " ".join(messages[4]["lines"])
assert proposal["requested_players"][0]["name"] in " ".join(messages[4]["lines"])
fixture = {
    "fps": 30, "durationInFrames": 750, "time": "9:41", "date": "Wednesday 9:41 AM",
    "messages": messages,
    "disclosure": "Fictional group-chat demo of an unofficial bot, not Adam Schefter. ESPN HTTP responses mocked; no live trade or message sent.",
    "verification": {
        "proposalId": proposal_id, "proposalStatus": stored["status"],
        "execution": stored["execution"],
        "providerCalls": [payload["type"] for payload in requests_seen],
        "unauthorizedAcceptanceBlocked": True, "duplicateAcceptanceBlocked": True,
        "acceptanceReply": acceptance, "waiverReply": waiver,
    },
    "provenance": {
        "waiver": "Real schefter.formatter.format_activity output against a fictional activity.",
        "trade": "Real trades.create -> trades.bare_response -> espn_trade.execute -> _post; only ESPN HTTP and league data mocked.",
        "acceptance": "Verbatim bare_response output. Submitted does not assert final league processing or roster settlement.",
        "offerSummary": "Scripted presentation of the verified proposal, not a captured LLM response.",
        "humanMessages": "Scripted fictional dialogue. No real contacts, messages, cookies, or league IDs loaded.",
    },
}
target = ROOT / "promo-video/src/trade-demo.json"
target.write_text(json.dumps(fixture, indent=2) + "\n")
print(f"PASS: {proposal_id}: pending -> recipient accepted -> ESPN proposal + acceptance (HTTP mocked)")
print("PASS: proposer/bystander blocked, no pre-consent calls, duplicate blocked; zero live requests")
print(f"Generated {len(messages)} messages, 25 seconds: {target.relative_to(ROOT)}")
