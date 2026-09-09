"""Durable, identity-gated trade proposals initiated from iMessage."""
import hashlib
import hmac
import json
import threading
import urllib.request
import uuid
from copy import deepcopy
from datetime import datetime

from . import config, espn, espn_trade

_lock = threading.Lock()
_DEFAULT = {"proposals": []}


def _now() -> str:
    return datetime.now(config.TZ).isoformat()


def _load() -> dict:
    if not config.TRADE_STATE_FILE.exists():
        return deepcopy(_DEFAULT)
    try:
        with open(config.TRADE_STATE_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return deepcopy(_DEFAULT)
    data.setdefault("proposals", [])
    return data


def _save(data: dict) -> None:
    tmp = config.TRADE_STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(config.TRADE_STATE_FILE)


def _manager_team(sender: str) -> str | None:
    needle = sender.strip().casefold()
    for address, team in config.TRADE_MANAGERS.items():
        if str(address).strip().casefold() == needle:
            return str(team)
    return None


def _find_team(name: str):
    needle = name.strip().casefold()
    matches = [
        team for team in espn.get_league().teams
        if needle == str(getattr(team, "team_name", "")).strip().casefold()
        or needle == str(getattr(team, "owner", "")).strip().casefold()
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one exact team/owner match for {name!r}; found {len(matches)}")
    return matches[0]


def _manager_for_team(team_name: str) -> str | None:
    needle = team_name.strip().casefold()
    matches = [address for address, mapped in config.TRADE_MANAGERS.items()
               if str(mapped).strip().casefold() == needle]
    return str(matches[0]) if len(matches) == 1 else None


def _players(team, names: list[str]) -> list[dict]:
    roster = list(getattr(team, "roster", []))
    result = []
    for requested in names:
        needle = requested.strip().casefold()
        matches = [p for p in roster if needle == str(getattr(p, "name", "")).strip().casefold()]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one exact roster match for {requested!r} on {getattr(team, 'team_name', 'team')}; "
                f"found {len(matches)}"
            )
        player = matches[0]
        result.append({"id": getattr(player, "playerId", None), "name": getattr(player, "name", requested)})
    return result


def _public(proposal: dict) -> dict:
    return {key: value for key, value in proposal.items() if not key.endswith("_sender")}


def create(sender: str, target_team: str, offered_players: list[str], requested_players: list[str]) -> dict:
    if not config.TRADE_ENABLED:
        return {"error": "In-chat trades are disabled"}
    source_name = _manager_team(sender)
    if not source_name:
        return {"error": "Your iMessage address is not mapped to a fantasy team"}
    try:
        source = _find_team(source_name)
        target = _find_team(target_team)
        resolved_target = str(getattr(target, "team_name", target_team))
        target_sender = _manager_for_team(resolved_target)
        if not target_sender:
            return {"error": f"No iMessage manager is mapped to {resolved_target}"}
        if target_sender.strip().casefold() == sender.strip().casefold():
            return {"error": "A manager cannot propose a trade to their own team"}
        give = _players(source, offered_players)
        receive = _players(target, requested_players)
        if not give or not receive:
            return {"error": "A trade must include at least one player from each team"}
    except ValueError as exc:
        return {"error": str(exc)}

    proposal = {
        "id": uuid.uuid4().hex[:8],
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
        "proposer_team": str(getattr(source, "team_name", source_name)),
        "recipient_team": resolved_target,
        "proposer_sender": sender,
        "recipient_sender": target_sender,
        "offered_players": give,
        "requested_players": receive,
        "execution": {"status": "waiting_for_acceptance"},
    }
    with _lock:
        data = _load()
        data["proposals"].append(proposal)
        _save(data)
    return {"proposal": _public(proposal)}


def pending(sender: str) -> dict:
    with _lock:
        rows = [p for p in _load()["proposals"] if p["status"] == "pending" and
                sender.strip().casefold() in (p["proposer_sender"].strip().casefold(),
                                               p["recipient_sender"].strip().casefold())]
    return {"proposals": [_public(p) for p in rows]}


def _execute(proposal: dict) -> dict:
    provider = config.TRADE_EXECUTION_PROVIDER
    if provider == "espn":
        return espn_trade.execute(proposal)
    if provider not in ("none", "webhook"):
        return {"status": "configuration_error", "message": "Unknown trade execution provider"}
    url = config.TRADE_EXECUTION_WEBHOOK_URL
    if provider == "none":
        return {"status": "approval_recorded", "message": "No provider execution hook is configured"}
    if not url:
        return {"status": "configuration_error", "message": "Trade execution webhook is not configured"}
    if not url.lower().startswith("https://") or not config.TRADE_EXECUTION_SECRET:
        return {"status": "configuration_error", "message": "Execution requires an HTTPS URL and signing secret"}
    try:
        source = _find_team(proposal["proposer_team"])
        target = _find_team(proposal["recipient_team"])
        _players(source, [p["name"] for p in proposal["offered_players"]])
        _players(target, [p["name"] for p in proposal["requested_players"]])
    except ValueError:
        return {"status": "validation_failed", "message": "Roster ownership changed before submission"}
    body = json.dumps(_public(proposal), separators=(",", ":")).encode()
    signature = hmac.new(config.TRADE_EXECUTION_SECRET.encode(), body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Schefter-Signature": f"sha256={signature}",
            "X-Schefter-Event-Id": proposal["id"],
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return {"status": "submitted", "http_status": response.status}
    except Exception as exc:
        return {"status": "failed", "message": f"Provider request failed ({type(exc).__name__})"}


def respond(sender: str, decision: str, proposal_id: str | None = None) -> dict:
    choice = decision.strip().casefold()
    if choice not in ("accept", "reject"):
        return {"error": "Decision must be accept or reject"}
    with _lock:
        data = _load()
        eligible = [p for p in data["proposals"] if p["status"] == "pending"
                    and p["recipient_sender"].strip().casefold() == sender.strip().casefold()
                    and (proposal_id is None or p["id"].casefold() == proposal_id.strip().casefold())]
        if not eligible:
            return {"error": "No pending trade request was found for you"}
        if len(eligible) > 1:
            return {"error": "More than one trade is pending; include the proposal ID"}
        proposal = eligible[0]
        proposal["status"] = "accepted" if choice == "accept" else "rejected"
        proposal["updated_at"] = _now()
        if choice == "accept":
            proposal["execution"] = {"status": "accepted_awaiting_submission"}
        else:
            proposal["execution"] = {"status": "not_applicable"}
        _save(data)

    # Never hold the state lock during network I/O. Persist the execution result
    # afterward, without changing the managers' recorded agreement.
    if choice == "accept":
        execution = _execute(proposal)
        with _lock:
            data = _load()
            stored = next((p for p in data["proposals"] if p["id"] == proposal["id"]), None)
            if stored is not None:
                stored["execution"] = execution
                stored["updated_at"] = _now()
                proposal = stored
                _save(data)
    return {"proposal": _public(proposal)}


def bare_response(sender: str, text: str) -> str | None:
    """Resolve an unprefixed yes/no only when it unambiguously targets a trade."""
    if not config.TRADE_ENABLED or not config.TRADE_ALLOW_BARE_RESPONSES:
        return None
    choices = {"yes": "accept", "accept": "accept", "no": "reject", "reject": "reject", "decline": "reject"}
    decision = choices.get(text.strip().casefold())
    if not decision:
        return None
    result = respond(sender, decision)
    proposal = result.get("proposal")
    if not proposal:
        return None
    verb = "accepted" if proposal["status"] == "accepted" else "rejected"
    execution = proposal.get("execution", {}).get("status")
    suffix = ""
    if verb == "accepted" and execution == "approval_recorded":
        suffix = " Agreement recorded; provider submission is not configured."
    elif verb == "accepted" and execution == "submitted":
        suffix = " The provider submission was sent."
    elif verb == "accepted" and execution in ("failed", "configuration_error", "validation_failed"):
        suffix = " Agreement recorded, but provider submission failed; the commissioner should verify it."
    return f"Trade {proposal['id']} {verb}.{suffix}"
