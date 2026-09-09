"""Plain-text group polls, tallied from ordinary iMessage replies.

Apple exposes no sanctioned way to create a native Polls balloon, so this
posts a numbered question and counts unprefixed replies instead. That trade
costs the tappable UI but buys something native polls cannot do here: the bot
reads its own results, so it can report a tally in chat.

Votes are recorded silently. Fourteen people voting must not produce fourteen
confirmation texts, which is the fastest way to get the bot muted.
"""
import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime

from . import config, imessage

MIN_OPTIONS = 2
MAX_OPTIONS = 9  # single-digit replies keep bare-number voting unambiguous
MAX_OPTION_CHARS = 120
MAX_QUESTION_CHARS = 300

_lock = threading.Lock()
_DEFAULT = {"polls": []}


def _now() -> str:
    return datetime.now(config.TZ).isoformat()


def _load() -> dict:
    if not config.POLL_STATE_FILE.exists():
        return deepcopy(_DEFAULT)
    try:
        with open(config.POLL_STATE_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return deepcopy(_DEFAULT)
    data.setdefault("polls", [])
    return data


def _save(data: dict) -> None:
    tmp = config.POLL_STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(config.POLL_STATE_FILE)


def _open_poll(data: dict) -> dict | None:
    return next((p for p in data["polls"] if p["status"] == "open"), None)


def _clean_question(question: str) -> str:
    cleaned = " ".join(str(question).split())
    if not cleaned:
        raise ValueError("A poll question is required")
    if len(cleaned) > MAX_QUESTION_CHARS:
        raise ValueError(f"Poll questions are limited to {MAX_QUESTION_CHARS} characters")
    return cleaned


def _clean_options(options) -> list[str]:
    if not isinstance(options, list):
        raise ValueError("Poll options must be a list")
    cleaned, seen = [], set()
    for raw in options:
        option = " ".join(str(raw).split())
        if not option:
            raise ValueError("Poll options cannot be empty")
        if len(option) > MAX_OPTION_CHARS:
            raise ValueError(f"Poll options are limited to {MAX_OPTION_CHARS} characters")
        folded = option.casefold()
        if folded in seen:
            raise ValueError("Poll options must be unique")
        seen.add(folded)
        cleaned.append(option)
    if not MIN_OPTIONS <= len(cleaned) <= MAX_OPTIONS:
        raise ValueError(f"Polls require {MIN_OPTIONS} to {MAX_OPTIONS} options")
    return cleaned


def _counts(poll: dict) -> list[int]:
    counts = [0] * len(poll["options"])
    for choice in poll["votes"].values():
        if 0 <= choice < len(counts):
            counts[choice] += 1
    return counts


def format_poll(poll: dict) -> str:
    lines = [f"POLL: {poll['question']}"]
    lines += [f"{i}. {option}" for i, option in enumerate(poll["options"], start=1)]
    lines.append("Reply with a number to vote.")
    return "\n".join(lines)


def format_results(poll: dict) -> str:
    counts = _counts(poll)
    total = sum(counts)
    label = "POLL RESULTS" if poll["status"] == "closed" else "POLL STANDINGS"
    lines = [f"{label}: {poll['question']}"]
    lines += [
        f"{i}. {option}: {count}"
        for i, (option, count) in enumerate(zip(poll["options"], counts), start=1)
    ]
    if not total:
        lines.append("No votes yet.")
        return "\n".join(lines)

    best = max(counts)
    leaders = [poll["options"][i] for i, count in enumerate(counts) if count == best]
    plural = "vote" if total == 1 else "votes"
    if len(leaders) == 1:
        verdict = f"{leaders[0]} {'wins' if poll['status'] == 'closed' else 'leads'}."
    else:
        verdict = "Tied: " + ", ".join(leaders) + "."
    lines.append(f"{total} {plural}. {verdict}")
    return "\n".join(lines)


def create(question: str, options) -> dict:
    """Open a poll and post it. Refuses while another is open so votes stay unambiguous.

    The poll text is sent here rather than returned for the model to repeat:
    the numbers people reply with are only meaningful if the posted options
    match the stored ones exactly.
    """
    if not config.POLLS_ENABLED:
        return {"error": "Polls are disabled"}
    try:
        cleaned_question = _clean_question(question)
        cleaned_options = _clean_options(options)
    except ValueError as exc:
        return {"error": str(exc)}

    with _lock:
        data = _load()
        existing = _open_poll(data)
        if existing is not None:
            return {
                "error": (
                    f"A poll is already open: {existing['question']!r}. "
                    "Close it before starting another."
                )
            }
        poll = {
            "id": uuid.uuid4().hex[:8],
            "status": "open",
            "created_at": _now(),
            "updated_at": _now(),
            "question": cleaned_question,
            "options": cleaned_options,
            "votes": {},
        }
        data["polls"].append(poll)
        _save(data)

    try:
        imessage.send(format_poll(poll))
    except Exception as exc:
        # Never leave an unposted poll open; bare numbers would be read as
        # votes on a poll nobody saw.
        with _lock:
            data = _load()
            data["polls"] = [p for p in data["polls"] if p["id"] != poll["id"]]
            _save(data)
        return {"error": f"The poll could not be posted ({type(exc).__name__})"}
    return {"poll": poll, "posted": True}


def results() -> dict:
    with _lock:
        data = _load()
        poll = _open_poll(data) or (data["polls"][-1] if data["polls"] else None)
    if poll is None:
        return {"error": "No poll has been created yet"}
    return {"poll": poll, "message": format_results(poll)}


def close() -> dict:
    with _lock:
        data = _load()
        poll = _open_poll(data)
        if poll is None:
            return {"error": "No poll is currently open"}
        poll["status"] = "closed"
        poll["updated_at"] = _now()
        _save(data)
    return {"poll": poll, "message": format_results(poll)}


def parse_vote(text: str) -> int | None:
    """Zero-based option index for a bare reply, or None if it isn't a vote.

    Pure read: the caller claims the message for dedup before recording.
    """
    if not config.POLLS_ENABLED:
        return None
    candidate = text.strip().strip(".!)").casefold()
    if not candidate:
        return None
    with _lock:
        poll = _open_poll(_load())
    if poll is None:
        return None
    if candidate.isdigit():
        index = int(candidate) - 1
        return index if 0 <= index < len(poll["options"]) else None
    for index, option in enumerate(poll["options"]):
        if candidate == option.casefold():
            return index
    return None


def record_vote(sender: str, choice: int) -> None:
    """Record one vote per sender. A later vote replaces an earlier one."""
    with _lock:
        data = _load()
        poll = _open_poll(data)
        if poll is None or not 0 <= choice < len(poll["options"]):
            return
        poll["votes"][sender.strip().casefold()] = choice
        poll["updated_at"] = _now()
        _save(data)
