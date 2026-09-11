"""Durable, identity-gated trade proposals initiated from iMessage."""
import difflib
import hashlib
import hmac
import json
import re
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


def _normalize(value: str) -> str:
    """Casefold and collapse whitespace. ESPN stores stray double and trailing
    spaces ("Team One "), which exact matching would trip over."""
    return " ".join(str(value).split()).casefold()


def _identifiers(team) -> set[str]:
    """Every name this team answers to: its own, plus its owners'.

    Team names change between seasons and mid-season; people do not. Accepting
    the owner's name means a mapping survives a rename.
    """
    names = {_normalize(getattr(team, "team_name", ""))}
    for owner in getattr(team, "owners", None) or []:
        if isinstance(owner, dict):
            first = (owner.get("firstName") or "").strip()
            last = (owner.get("lastName") or "").strip()
            # First name included because people address each other that way
            # ("offer taylor puka for mccaffrey"). _find_team refuses a tie, so
            # a league with two Taylors declines rather than picking one.
            names.update(_normalize(n) for n in (f"{first} {last}", last, first) if n.strip())
        elif owner:
            names.add(_normalize(owner))
    # Older espn-api exposed a plain string here; harmless when absent.
    if getattr(team, "owner", None):
        names.add(_normalize(team.owner))
    names.discard("")
    return names


def _find_team(name: str):
    """Resolve a team from whatever people call it.

    Tiered so "Rebuild" finds "Taylor's Rebuild" without a loose
    substring rule picking the wrong team, and a tie at any precision is
    refused rather than guessed.
    """
    needle = _normalize(name)
    if not needle:
        raise ValueError(f"Expected one exact team/owner match for {name!r}; found 0")

    exact, word, partial = [], [], []
    for team in espn.get_league().teams:
        identifiers = _identifiers(team)
        if needle in identifiers:
            exact.append(team)
            continue
        joined = " ".join(identifiers)
        if needle in joined.replace("'", "").replace(".", "").split():
            word.append(team)
        elif len(needle) >= 3 and any(needle in i for i in identifiers):
            partial.append(team)

    for tier in (exact, word, partial):
        if len(tier) == 1:
            return tier[0]
        if len(tier) > 1:
            raise ValueError(
                f"Expected one exact team/owner match for {name!r}; found {len(tier)}"
            )
    raise ValueError(f"Expected one exact team/owner match for {name!r}; found 0")


def _same_team(a, b) -> bool:
    """Compare by id when both carry one; never let two missing ids look equal."""
    a_id = getattr(a, "team_id", None)
    b_id = getattr(b, "team_id", None)
    if a_id is not None and b_id is not None:
        return a_id == b_id
    return a is b


def _manager_for_team(team_name: str) -> str | None:
    """Address of whoever manages this team, however their mapping names them.

    Compares resolved teams rather than raw strings, so a mapping stored as an
    owner name still matches a team looked up by team name, and vice versa.
    """
    try:
        target = _find_team(team_name)
    except ValueError:
        return None
    matches = []
    for address, mapped in config.TRADE_MANAGERS.items():
        try:
            candidate = _find_team(str(mapped))
        except ValueError:
            continue  # a stale mapping should not block everyone else
        if _same_team(candidate, target):
            matches.append(address)
    return str(matches[0]) if len(matches) == 1 else None


def _initialisms(full_name: str) -> set[str]:
    """Short forms people use for a player: CMC, JSN, ARSB.

    Derived from the name rather than a nickname list, which would rot every
    time a roster turns over. "Mc"/"Mac" counts as its own syllable, which is
    what makes Christian McCaffrey "CMC" rather than "CM".
    """
    parts = [p for p in re.split(r"[\s\-'.]+", str(full_name)) if p]
    if not parts:
        return set()
    forms = {"".join(p[0] for p in parts)}
    split = []
    for part in parts:
        low = part.casefold()
        if low.startswith("mc") and len(part) > 2:
            split += [part[:2], part[2:]]
        elif low.startswith("mac") and len(part) > 3:
            split += [part[:3], part[3:]]
        else:
            split.append(part)
    forms.add("".join(p[0] for p in split))
    return {f.casefold() for f in forms if len(f) >= 3}


def _match_player(roster, requested: str):
    """One player on this roster, matched the way people actually name them.

    Nobody types "Kimani Vidal"; they say "Vidal". Tiered so a surname works
    without a loose substring rule pulling in the wrong player, and a tie at
    any precision is refused rather than guessed.
    """
    needle = _normalize(requested)
    exact, word, initials, partial = [], [], [], []
    for player in roster:
        name = _normalize(getattr(player, "name", ""))
        if not name:
            continue
        if name == needle:
            exact.append(player)
        elif needle in name.replace(".", "").replace("'", "").split():
            word.append(player)
        elif needle in _initialisms(getattr(player, "name", "")):
            initials.append(player)
        elif len(needle) >= 3 and needle in name:
            partial.append(player)
    for tier in (exact, word, initials, partial):
        if len(tier) == 1:
            return tier[0]
        if len(tier) > 1:
            return None  # ambiguous at this precision

    # Last resort, typos: "mcaffery" for "McCaffrey", "jamar" for "Ja'Marr".
    # Compared against surnames too, since that is what people type.
    if len(needle) >= 4:
        candidates = {}
        for player in roster:
            full = _normalize(getattr(player, "name", ""))
            if not full:
                continue
            candidates.setdefault(full, player)
            candidates.setdefault(full.split()[-1], player)
        close = difflib.get_close_matches(needle, list(candidates), n=2, cutoff=0.8)
        if len(close) == 1 or (len(close) > 1 and candidates[close[0]] is candidates[close[1]]):
            return candidates[close[0]]
    return None


def _players(team, names: list[str]) -> list[dict]:
    roster = list(getattr(team, "roster", []))
    result = []
    for requested in names:
        player = _match_player(roster, requested)
        if player is None:
            raise ValueError(
                f"Expected one roster match for {requested!r} on "
                f"{getattr(team, 'team_name', 'team')}; found none or several"
            )
        result.append({
            "id": getattr(player, "playerId", None),
            "name": getattr(player, "name", requested),
            "position": getattr(player, "position", None),
            "nfl_team": getattr(player, "proTeam", None),
        })
    return result


def _describe(player: dict) -> str:
    """"WR Puka Nacua (LAR)", degrading gracefully when ESPN omits a field."""
    label = " ".join(part for part in (player.get("position"), player.get("name")) if part)
    team = player.get("nfl_team")
    return f"{label} ({team})" if team and team not in ("None", "FA") else label


def describe_proposal(proposal: dict) -> str:
    """The message the chat sees. Fixed wording, no commentary.

    Written here rather than left to the model, which otherwise paraphrases
    the terms away or replaces them with its opinion of the trade.
    """
    give = ", ".join(_describe(p) for p in proposal["offered_players"])
    get = ", ".join(_describe(p) for p in proposal["requested_players"])
    return (
        f"Trade {proposal['id']} proposed. {proposal['proposer_team']} sends {give}. "
        f"{proposal['recipient_team']} sends {get}. "
        f"Awaiting a reply from {proposal['recipient_team']}."
    )


def _public(proposal: dict) -> dict:
    return {key: value for key, value in proposal.items() if not key.endswith("_sender")}


def _owner_of(player_name: str, exclude=None):
    """The one team rostering this player, or None if it is not exactly one."""
    matches = [
        team for team in espn.get_league().teams
        if (exclude is None or not _same_team(team, exclude))
        and _match_player(getattr(team, "roster", []), player_name) is not None
    ]
    return matches[0] if len(matches) == 1 else None


def _split_out_target(source_name: str, offered_players: list[str]):
    """Separate a recipient's name that arrived in the offered-players list.

    Returns (players actually on the sender's roster, name of the team the
    stray entry identified). Only drops an entry when it is both absent from
    the sender's roster and a real team or owner, so a genuine player is never
    silently discarded.
    """
    try:
        source = _find_team(source_name)
    except ValueError:
        return list(offered_players or []), None

    roster = getattr(source, "roster", [])
    kept, named = [], None
    for entry in offered_players or []:
        if _match_player(roster, entry) is not None:
            kept.append(entry)
            continue
        try:
            team = _find_team(entry)
        except ValueError:
            kept.append(entry)  # unknown, let the roster check report it
            continue
        if not _same_team(team, source) and named is None:
            named = entry
        else:
            kept.append(entry)
    return kept, named


def _resolve_target(target_team: str, requested_players: list[str], source):
    """Find who is being traded with.

    People name the player they want, not the team that has him ("offer Vidal
    for Brock Bowers"), so the model ends up putting a player in the team slot
    or leaving it blank. A player sits on exactly one roster, so when the given
    team does not resolve, derive it from who actually owns the players asked
    for, provided they all point at the same team.
    """
    candidate = None
    if target_team and str(target_team).strip():
        try:
            candidate = _find_team(target_team)
        except ValueError:
            candidate = None
    # With no team named, the model fills the slot with whatever is at hand:
    # the player, an empty string, or the asker's own team. None of those is
    # the counterparty, so fall through to deriving it from the roster.
    if candidate is not None and not _same_team(candidate, source):
        return candidate

    owners = [_owner_of(name, exclude=source) for name in requested_players or []]
    owners = [team for team in owners if team is not None]
    if owners and all(_same_team(team, owners[0]) for team in owners):
        return owners[0]

    raise ValueError(
        f"Expected one exact team/owner match for {target_team!r}; found 0"
    )


def create(sender: str, target_team: str, offered_players: list[str], requested_players: list[str]) -> dict:
    if not config.TRADE_ENABLED:
        return {"error": "In-chat trades are disabled"}
    source_name = _manager_team(sender)
    if not source_name:
        return {"error": "Your iMessage address is not mapped to a fantasy team"}
    # "offer taylor puka for mccaffrey" names the recipient inline, and the model
    # passes "Taylor" through as a player. Anyone in the offered list who is not
    # on the sender's roster but does name a team is the counterparty.
    offered_players, named_target = _split_out_target(source_name, offered_players)
    target_team = target_team or named_target
    try:
        source = _find_team(source_name)
        target = _resolve_target(target_team or named_target, requested_players, source)
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
    return {"proposal": _public(proposal), "message": describe_proposal(proposal)}


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
