"""ESPN trade writer matching the transaction contract used by ESPN's web app.

This API is undocumented and unsupported by ESPN. All callers must validate
manager consent and current roster ownership before reaching this module.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests

from . import config, espn

WRITE_ROOT = "https://lm-api-writes.fantasy.espn.com/apis/v3/games/ffl"
PLATFORM_VERSION = "5e254affd13eaa961c7dffbd9de59d867a2e0acf"


@dataclass(frozen=True)
class Credentials:
    espn_s2: str
    swid: str


class EspnTradeError(RuntimeError):
    pass


def _credentials_file() -> dict:
    path = config.ESPN_TRADE_CREDENTIALS_FILE
    if path is None:
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise EspnTradeError("ESPN team credentials file could not be read") from exc
    if not isinstance(data, dict):
        raise EspnTradeError("ESPN team credentials file must contain a JSON object")
    return data


def _credentials(team_name: str) -> Credentials:
    if config.ESPN_TRADE_AUTH_MODE == "league_manager":
        espn_s2, swid = config.ESPN_S2, config.SWID
    elif config.ESPN_TRADE_AUTH_MODE == "team_credentials":
        row = _credentials_file().get(team_name, {})
        espn_s2 = row.get("espn_s2") if isinstance(row, dict) else None
        swid = row.get("swid") if isinstance(row, dict) else None
    else:
        raise EspnTradeError("ESPN_TRADE_AUTH_MODE must be league_manager or team_credentials")
    if not espn_s2 or not swid:
        raise EspnTradeError(f"ESPN credentials are not configured for {team_name}")
    return Credentials(str(espn_s2), str(swid))


def _team(name: str):
    needle = name.strip().casefold()
    matches = [team for team in espn.get_league().teams
               if str(getattr(team, "team_name", "")).strip().casefold() == needle]
    if len(matches) != 1:
        raise EspnTradeError(f"Could not resolve one ESPN team for {name}")
    return matches[0]


def _transaction_url() -> str:
    return (
        f"{WRITE_ROOT}/seasons/{config.SEASON}/segments/0/"
        f"leagues/{config.LEAGUE_ID}/transactions/"
    )


def _headers() -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Fantasy-Source": "kona",
        "X-Fantasy-Platform": "espn-fantasy-web",
        "X-Fantasy-Platform-Version": PLATFORM_VERSION,
    }


def _post(payload: dict, credentials: Credentials) -> dict:
    try:
        response = requests.post(
            _transaction_url(),
            data=json.dumps(payload, separators=(",", ":")),
            headers=_headers(),
            cookies={"espn_s2": credentials.espn_s2, "SWID": credentials.swid},
            timeout=config.ESPN_TRADE_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise EspnTradeError(f"ESPN request failed ({type(exc).__name__})") from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400:
        code = _error_code(data)
        suffix = f" ({code})" if code else ""
        raise EspnTradeError(f"ESPN rejected the trade with HTTP {response.status_code}{suffix}")
    return data


def _error_code(data) -> str | None:
    if isinstance(data, dict):
        details = data.get("details") or data.get("messages") or []
        if isinstance(details, list) and details:
            first = details[0]
            if isinstance(first, dict):
                value = first.get("type") or first.get("code")
                return str(value) if value else None
    return None


def _transaction_id(data) -> str | None:
    """Find ESPN's returned ID without depending on one response wrapper."""
    if isinstance(data, dict):
        for key in ("id", "transactionId"):
            value = data.get(key)
            if value is not None:
                return str(value)
        for key in ("transaction", "transactions", "response"):
            found = _transaction_id(data.get(key))
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _transaction_id(item)
            if found:
                return found
    return None


def _base_payload(team_id: int, credentials: Credentials, transaction_type: str) -> dict:
    league = espn.get_league()
    scoring_period = getattr(league, "scoringPeriodId", None) or getattr(league, "current_week", 1)
    payload = {
        "isLeagueManager": config.ESPN_TRADE_AUTH_MODE == "league_manager",
        "teamId": int(team_id),
        "type": transaction_type,
        "memberId": credentials.swid,
        "scoringPeriodId": int(scoring_period),
        "executionType": "EXECUTE",
    }
    if config.ESPN_TRADE_AUTH_MODE == "league_manager":
        payload.update({"isActingAsTeamOwner": True, "skipTransactionCounters": False})
    return payload


def _proposal_payload(proposal: dict, source, target, credentials: Credentials) -> dict:
    payload = _base_payload(source.team_id, credentials, "TRADE_PROPOSAL")
    payload.update({
        "expirationDate": int((datetime.now(config.TZ) + timedelta(days=2)).timestamp() * 1000),
        "comment": f"Accepted via Schefter Bot trade {proposal['id']}",
        "items": [
            *({"playerId": int(player["id"]), "type": "TRADE",
               "fromTeamId": int(source.team_id), "toTeamId": int(target.team_id)}
              for player in proposal["offered_players"]),
            *({"playerId": int(player["id"]), "type": "TRADE",
               "fromTeamId": int(target.team_id), "toTeamId": int(source.team_id)}
              for player in proposal["requested_players"]),
        ],
    })
    return payload


def execute(proposal: dict) -> dict:
    """Create and accept the ESPN trade after both iMessage managers consent."""
    if not config.ESPN_TRADE_WRITE_ENABLED:
        return {"status": "configuration_error", "message": "ESPN trade writes are disabled"}
    if config.LEAGUE_ID is None:
        return {"status": "configuration_error", "message": "ESPN league is not configured"}
    transaction_id = None
    phase = "proposal"
    try:
        source = _team(proposal["proposer_team"])
        target = _team(proposal["recipient_team"])
        proposer_credentials = _credentials(proposal["proposer_team"])
        recipient_credentials = _credentials(proposal["recipient_team"])
        proposed = _post(
            _proposal_payload(proposal, source, target, proposer_credentials),
            proposer_credentials,
        )
        transaction_id = _transaction_id(proposed)
        if not transaction_id:
            raise EspnTradeError("ESPN created the proposal but returned no transaction ID")
        phase = "acceptance"
        accept = _base_payload(target.team_id, recipient_credentials, "TRADE_ACCEPT")
        accept["relatedTransactionId"] = transaction_id
        _post(accept, recipient_credentials)
        return {"status": "submitted", "provider": "espn", "transaction_id": transaction_id}
    except (EspnTradeError, TypeError, ValueError) as exc:
        result = {"status": "failed", "provider": "espn", "phase": phase, "message": str(exc)}
        if transaction_id:
            result["transaction_id"] = transaction_id
        return result
