"""Durable deduplication and short conversation history for chat replies."""
import json
import threading
from copy import deepcopy

from . import config

_MAX_PROCESSED = 1000
_lock = threading.Lock()
_DEFAULT = {"processed": [], "history": {}}


def load() -> dict:
    if not config.AGENT_STATE_FILE.exists():
        return deepcopy(_DEFAULT)
    try:
        with open(config.AGENT_STATE_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return deepcopy(_DEFAULT)
    data.setdefault("processed", [])
    data.setdefault("history", {})
    return data


def save(data: dict) -> None:
    data["processed"] = data.get("processed", [])[-_MAX_PROCESSED:]
    history_size = max(2, config.AGENT_HISTORY_SIZE * 2)
    for chat_id, messages in data.get("history", {}).items():
        data["history"][chat_id] = messages[-history_size:]
    tmp = config.AGENT_STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(config.AGENT_STATE_FILE)


def claim(message_id: str) -> bool:
    """Atomically record a message ID. False means it was already handled."""
    with _lock:
        data = load()
        if message_id in data["processed"]:
            return False
        data["processed"].append(message_id)
        save(data)
        return True


def history(chat_id: str) -> list[dict]:
    with _lock:
        return list(load()["history"].get(chat_id, []))


def append_exchange(chat_id: str, sender: str, question: str, answer: str) -> None:
    with _lock:
        data = load()
        messages = data["history"].setdefault(chat_id, [])
        messages.extend([
            {"role": "user", "content": f"{sender}: {question}"},
            {"role": "assistant", "content": answer},
        ])
        save(data)
