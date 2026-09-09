"""Configuration loaded from .env next to the project root."""
import os
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# --- ESPN ---
# Left as None when unset so `python -m schefter.chats` works before setup;
# espn.py raises a clear error if it's still missing at fetch time.
_lid = os.environ.get("ESPN_LEAGUE_ID")
LEAGUE_ID = int(_lid) if _lid else None
SEASON = int(os.environ.get("ESPN_SEASON", "2026"))

# Only needed for private leagues. Pulled from the espn.com cookies.
ESPN_S2 = os.environ.get("ESPN_S2") or None
SWID = os.environ.get("ESPN_SWID") or None

# --- iMessage ---
# The iMessage group chat GUID, e.g. "iMessage;+;chatYOUR_GROUP_ID".
# Run `python -m schefter.chats` to list the ones on this Mac.
CHAT_ID = os.environ.get("IMESSAGE_CHAT_ID", "")

# --- Polls ---
# Plain-text polls tallied from unprefixed replies. Turning this off also stops
# bare numbers ("2") from being read as votes.
POLLS_ENABLED = _flag("POLLS_ENABLED", True)
POLL_STATE_FILE = Path(os.environ.get("POLL_STATE_FILE", ROOT / "poll-state.json"))

# --- League history ---
# Completed seasons never change, so they are fetched once and cached here.
HISTORY_CACHE_FILE = Path(os.environ.get("HISTORY_CACHE_FILE", ROOT / "history-cache.json"))
# Aggregates (all-time records, superlatives) are answered in SQL rather than
# by handing the model every standings row to sum in its own context.
HISTORY_DB_FILE = Path(os.environ.get("HISTORY_DB_FILE", ROOT / "history.db"))

# --- Interactive agent ---
# BlueBubbles delivers incoming iMessages to this local webhook. Keep the
# listener on loopback unless you deliberately put an authenticated proxy in
# front of it.
AGENT_ENABLED = _flag("AGENT_ENABLED", False)
AGENT_HOST = os.environ.get("AGENT_HOST", "127.0.0.1")
AGENT_PORT = int(os.environ.get("AGENT_PORT", "8765"))
AGENT_WEBHOOK_SECRET = os.environ.get("AGENT_WEBHOOK_SECRET", "")
AGENT_TRIGGER = os.environ.get("AGENT_TRIGGER", "schefter").strip()
AGENT_HISTORY_SIZE = int(os.environ.get("AGENT_HISTORY_SIZE", "10"))
AGENT_MAX_REPLY_CHARS = int(os.environ.get("AGENT_MAX_REPLY_CHARS", "1800"))
AGENT_MAX_QUESTION_CHARS = int(os.environ.get("AGENT_MAX_QUESTION_CHARS", "1200"))
AGENT_STATE_FILE = Path(os.environ.get("AGENT_STATE_FILE", ROOT / "agent-state.json"))

# The OpenAI SDK reads OPENAI_API_KEY directly from the environment.
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
AGENT_WEB_SEARCH = _flag("AGENT_WEB_SEARCH", True)

# --- In-chat trades ---
# Exact iMessage sender address -> fantasy team name. JSON keeps phone numbers
# and email addresses intact, e.g. {"+15551234567":"Team One"}.
try:
    _trade_managers = json.loads(os.environ.get("TRADE_MANAGERS", "{}"))
except json.JSONDecodeError:
    _trade_managers = {}
TRADE_MANAGERS = _trade_managers if isinstance(_trade_managers, dict) else {}
TRADE_ENABLED = _flag("TRADE_ENABLED", False)
TRADE_STATE_FILE = Path(os.environ.get("TRADE_STATE_FILE", ROOT / "trade-state.json"))
TRADE_ALLOW_BARE_RESPONSES = _flag("TRADE_ALLOW_BARE_RESPONSES", True)
# none, espn, or webhook. "none" records the two managers' agreement without
# contacting a fantasy provider.
TRADE_EXECUTION_PROVIDER = os.environ.get("TRADE_EXECUTION_PROVIDER", "none").strip().lower()
# Optional HTTPS endpoint that performs the provider-specific submission after
# both managers consent. Requests are signed with TRADE_EXECUTION_SECRET.
TRADE_EXECUTION_WEBHOOK_URL = os.environ.get("TRADE_EXECUTION_WEBHOOK_URL", "").strip()
TRADE_EXECUTION_SECRET = os.environ.get("TRADE_EXECUTION_SECRET", "")

# ESPN has no public write API. This adapter mirrors the transaction contract
# used by ESPN's web client and is deliberately protected by a second kill switch.
ESPN_TRADE_WRITE_ENABLED = _flag("ESPN_TRADE_WRITE_ENABLED", False)
ESPN_TRADE_AUTH_MODE = os.environ.get("ESPN_TRADE_AUTH_MODE", "league_manager").strip().lower()
_trade_credentials = os.environ.get("ESPN_TRADE_CREDENTIALS_FILE", "").strip()
ESPN_TRADE_CREDENTIALS_FILE = Path(_trade_credentials) if _trade_credentials else None
ESPN_TRADE_TIMEOUT = int(os.environ.get("ESPN_TRADE_TIMEOUT", "20"))

# --- Features ---
# Defaults are the "high signal" set: roughly 3-8 messages in a normal week.
FEATURES = {
    "transactions": _flag("FEATURE_TRANSACTIONS", True),
    "injuries": _flag("FEATURE_INJURIES", True),
    "inactives": _flag("FEATURE_INACTIVES", True),
    "recap": _flag("FEATURE_RECAP", True),
    "rankings": _flag("FEATURE_RANKINGS", True),
    "rumors": _flag("FEATURE_RUMORS", True),
    # Never auto-fires (see draft_lottery.should_run). This flag just gates
    # whether `--only draft_lottery` is allowed to run at all.
    "draft_lottery": _flag("FEATURE_DRAFT_LOTTERY", True),
}

# Most rostered players carry a Questionable tag at some point in the week;
# announcing all of them is the fastest way to get the bot muted.
ANNOUNCE_QUESTIONABLE = _flag("ANNOUNCE_QUESTIONABLE", False)

# NFL runs on Eastern regardless of where this Mac sits.
TZ = ZoneInfo(os.environ.get("TIMEZONE", "America/New_York"))

# Sunday inactive sweep: weekday 6 = Sunday. Window is inclusive of start hour,
# exclusive of end, in TZ. Default fires between 11am and 1pm ET (1pm kickoff).
INACTIVE_WINDOW = (11, 13)
# Recap + rankings land Tuesday morning, after Monday night finishes.
RECAP_WINDOW = (9, 12)

# Rumor mill: normally fires on a coin flip in the Tuesday/Thursday morning
# windows. Odds ramp from RUMOR_CHANCE_MIN up to RUMOR_CHANCE_PEAK over the
# RUMOR_RAMP_WEEKS before the league's trade deadline; the week before and
# the week of the deadline hold at RUMOR_CHANCE_PEAK with extra days in play
# (~3-4 rumors that week); after the deadline it settles at RUMOR_CHANCE_POST
# on the normal two-day cadence. Flat at RUMOR_CHANCE all season if the
# league has no trade deadline configured.
RUMOR_WINDOW = (9, 12)
RUMOR_CHANCE = float(os.environ.get("RUMOR_CHANCE", "0.65"))
RUMOR_CHANCE_MIN = float(os.environ.get("RUMOR_CHANCE_MIN", "0.25"))
RUMOR_CHANCE_PEAK = float(os.environ.get("RUMOR_CHANCE_PEAK", "0.9"))
RUMOR_CHANCE_POST = float(os.environ.get("RUMOR_CHANCE_POST", "0.75"))
RUMOR_RAMP_WEEKS = float(os.environ.get("RUMOR_RAMP_WEEKS", "8"))

# --- Tuning ---
FETCH_SIZE = int(os.environ.get("FETCH_SIZE", "25"))
MAX_PER_POLL = int(os.environ.get("MAX_PER_POLL", "6"))
STATE_FILE = Path(os.environ.get("STATE_FILE", ROOT / "state.json"))
DRY_RUN = _flag("DRY_RUN", False)
