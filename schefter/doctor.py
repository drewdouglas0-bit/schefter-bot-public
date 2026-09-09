"""Preflight checks. Run this first on a new machine. It tells you exactly
what's missing instead of making you decode a stack trace.

    ./venv/bin/python -m schefter.doctor
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from . import config

OK, FAIL, WARN = "  ok  ", " FAIL ", " warn "


def _p(status, label, detail=""):
    print(f"[{status}] {label}" + (f"\n         {detail}" if detail else ""))


def check_env():
    ok = True
    if not config.LEAGUE_ID:
        _p(FAIL, "ESPN_LEAGUE_ID", "Not set in .env. Find it in your league URL.")
        ok = False
    else:
        _p(OK, f"ESPN_LEAGUE_ID = {config.LEAGUE_ID}")

    if not config.CHAT_ID:
        _p(FAIL, "IMESSAGE_CHAT_ID", "Not set. Run: python -m schefter.chats")
        ok = False
    else:
        _p(OK, f"IMESSAGE_CHAT_ID = {config.CHAT_ID}")

    if not (config.ESPN_S2 and config.SWID):
        _p(WARN, "ESPN cookies not set", "Fine for public leagues; required for private ones.")
    else:
        _p(OK, "ESPN cookies present")
    return ok


def check_messages():
    """Confirms Messages.app is running and this terminal may drive it."""
    script = 'tell application "System Events" to (name of processes) contains "Messages"'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        _p(FAIL, "Messages.app automation", r.stderr.strip() or
           "Grant System Settings > Privacy & Security > Automation > Terminal > Messages")
        return False
    if r.stdout.strip() != "true":
        _p(WARN, "Messages.app is not running", "Open it and leave it running, or the bot can't send.")
        return True
    _p(OK, "Messages.app running and scriptable")
    return True


def check_chat_exists():
    if not config.CHAT_ID:
        return False
    script = f'tell application "Messages" to get id of chat id "{config.CHAT_ID}"'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        _p(FAIL, "Target chat not found",
           "This Mac's Messages account can't see that chat. Is it signed into the "
           "bot's Apple ID, and has the bot been added to the group?")
        return False
    _p(OK, "Target chat is reachable")
    return True


def check_espn():
    if not config.LEAGUE_ID:
        return False
    try:
        from . import espn
        lg = espn.get_league()
        _p(OK, f"ESPN league: {lg.settings.name} ({len(lg.teams)} teams, week {lg.current_week})")
        n = len(lg.recent_activity(size=config.FETCH_SIZE))
        _p(OK, f"Activity feed reachable ({n} recent items)")
        return True
    except Exception as e:
        name = type(e).__name__
        hint = ""
        if "AccessDenied" in name:
            hint = "Private league: espn_s2 / SWID are missing, wrong, or expired."
        elif "InvalidLeague" in name:
            hint = "Check ESPN_LEAGUE_ID and ESPN_SEASON."
        _p(FAIL, f"ESPN: {name}", hint or str(e))
        return False


def check_agent():
    if not config.AGENT_ENABLED:
        _p(WARN, "Interactive agent disabled", "Set AGENT_ENABLED=1 after configuring BlueBubbles.")
        return True
    ok = True
    if not config.AGENT_WEBHOOK_SECRET:
        _p(FAIL, "AGENT_WEBHOOK_SECRET", "Set a long random value and put it in the BlueBubbles webhook URL.")
        ok = False
    else:
        _p(OK, "Agent webhook secret present")
    if not os.environ.get("OPENAI_API_KEY"):
        _p(FAIL, "OPENAI_API_KEY", "Create an API key and add it to .env.")
        ok = False
    else:
        _p(OK, f"OpenAI model = {config.OPENAI_MODEL}")
    if config.AGENT_HOST not in ("127.0.0.1", "localhost", "::1"):
        _p(FAIL, "AGENT_HOST", "Keep the webhook on loopback; BlueBubbles runs on the same Mac.")
        ok = False
    else:
        _p(OK, f"Agent listener = {config.AGENT_HOST}:{config.AGENT_PORT}")
    return check_listener_is_current() and ok


def _launchd_label() -> str:
    """This instance's listener label, so the fix can name the exact command.

    Several leagues run side by side with different labels, so the plist is
    matched on the directory it points at rather than assuming a name.
    """
    agents = Path.home() / "Library" / "LaunchAgents"
    target = str(config.ROOT / "run-agent.sh")
    try:
        for plist in agents.glob("com.schefterbot*.plist"):
            if target in plist.read_text():
                return plist.stem
    except OSError:
        pass
    return "com.schefterbot.listener"


def check_listener_is_current():
    """Catch a listener still serving code from before the last edit.

    Python loads modules once at startup, so a running listener keeps the old
    code until it is restarted. That looks exactly like a fix not working.
    """
    url = f"http://{config.AGENT_HOST}:{config.AGENT_PORT}/status"
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            status = json.loads(response.read())
    except Exception:
        _p(WARN, "Listener not reachable", f"Nothing answered {url}. Start it with ./install.sh")
        return True  # not running is a separate condition, reported elsewhere

    newest = 0.0
    try:
        newest = max(p.stat().st_mtime for p in (config.ROOT / "schefter").glob("*.py"))
    except ValueError:
        pass
    loaded = float(status.get("loaded_source") or 0)
    if newest > loaded:
        changed = datetime.fromtimestamp(newest).strftime("%b %d %H:%M")
        running = datetime.fromtimestamp(float(status.get("started_at") or 0)).strftime("%b %d %H:%M")
        _p(
            FAIL,
            "Listener is running older code",
            f"Started {running}; source changed {changed}. "
            f"Restart it: launchctl kickstart -k gui/$(id -u)/{_launchd_label()}",
        )
        return False
    _p(OK, "Listener is running the current code")
    return True


def check_trades():
    if not config.TRADE_ENABLED:
        _p(WARN, "In-chat trades disabled", "Set TRADE_ENABLED=1 after mapping every manager.")
        return True
    ok = True
    if len(config.TRADE_MANAGERS) < 2:
        _p(FAIL, "TRADE_MANAGERS", "Map at least two exact iMessage addresses to ESPN team names.")
        ok = False
    else:
        _p(OK, f"Trade manager mappings = {len(config.TRADE_MANAGERS)}")
    provider = config.TRADE_EXECUTION_PROVIDER
    if provider == "none":
        _p(WARN, "Trade execution disabled", "Approvals will be recorded but not sent to ESPN.")
    elif provider == "espn":
        if not config.ESPN_TRADE_WRITE_ENABLED:
            _p(FAIL, "ESPN trade writes", "Set ESPN_TRADE_WRITE_ENABLED=1 to enable the explicit write gate.")
            ok = False
        elif config.ESPN_TRADE_AUTH_MODE == "league_manager":
            if not (config.ESPN_S2 and config.SWID):
                _p(FAIL, "ESPN trade credentials", "League-manager mode requires ESPN_S2 and ESPN_SWID.")
                ok = False
            else:
                _p(WARN, "ESPN trade executor enabled",
                   "Unsupported ESPN write API; confirm this account is league manager before the first trade.")
        elif config.ESPN_TRADE_AUTH_MODE == "team_credentials":
            path = config.ESPN_TRADE_CREDENTIALS_FILE
            if path is None or not path.is_file():
                _p(FAIL, "ESPN team credentials file", "Set ESPN_TRADE_CREDENTIALS_FILE to a readable JSON file.")
                ok = False
            else:
                _p(WARN, "ESPN trade executor enabled",
                   "Per-team ESPN sessions are highly sensitive and the write API is unsupported.")
        else:
            _p(FAIL, "ESPN_TRADE_AUTH_MODE", "Use league_manager or team_credentials.")
            ok = False
    elif provider == "webhook":
        if not config.TRADE_EXECUTION_WEBHOOK_URL.startswith("https://") or not config.TRADE_EXECUTION_SECRET:
            _p(FAIL, "Trade execution webhook", "Configure an HTTPS URL and signing secret.")
            ok = False
        else:
            _p(OK, "Signed trade execution webhook configured")
    else:
        _p(FAIL, "TRADE_EXECUTION_PROVIDER", "Use none, espn, or webhook.")
        ok = False
    return ok


def main() -> int:
    print(f"\nschefter-bot preflight  ({config.ROOT})\n")
    results = [check_env(), check_messages(), check_chat_exists(), check_espn(), check_agent(), check_trades()]
    print()
    if all(results):
        print("All checks passed. Try:  ./venv/bin/python -m schefter.main --replay 10\n")
        return 0
    print("Fix the FAIL items above, then re-run.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
