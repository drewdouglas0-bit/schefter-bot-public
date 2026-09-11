"""Receives BlueBubbles webhooks and dispatches mention-gated agent replies.

    python -m schefter.listener
"""
import hashlib
import hmac
import json
import queue
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import agent, agent_state, config, guardrails, imessage, moderation, polls, trades


def log(message: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}", flush=True)


IMAGE_DECLINE_MESSAGE = "I can't view or edit photos — text only, sorry."


def source_fingerprint() -> float:
    """Newest mtime among this instance's modules."""
    try:
        return max(path.stat().st_mtime for path in (config.ROOT / "schefter").glob("*.py"))
    except ValueError:
        return 0.0


# Captured at import. Python loads modules once, so a long-running listener
# keeps serving whatever the code was when it started; doctor compares this
# against the files on disk to catch a forgotten restart.
STARTED_AT = datetime.now().timestamp()
LOADED_SOURCE = source_fingerprint()


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    chat_id: str
    sender: str
    text: str
    has_image: bool = False


def _has_image_attachment(data: dict) -> bool:
    for att in data.get("attachments") or []:
        if not isinstance(att, dict):
            continue
        mime = att.get("mimeType") or att.get("mime_type") or ""
        if isinstance(mime, str) and mime.lower().startswith("image/"):
            return True
    return False


def parse_event(payload: dict) -> IncomingMessage | None:
    if payload.get("type") != "new-message":
        return None
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("isFromMe"):
        return None
    text = data.get("text")
    chats = data.get("chats") or []
    if not isinstance(text, str) or not text.strip() or not chats:
        return None
    chat_id = chats[0].get("guid") if isinstance(chats[0], dict) else None
    if not chat_id:
        return None
    handle = data.get("handle") or {}
    if isinstance(handle, dict):
        sender = handle.get("address") or handle.get("id") or "League member"
    else:
        sender = str(handle) or "League member"
    message_id = data.get("guid") or data.get("id")
    if not message_id:
        raw = f"{chat_id}|{sender}|{text}|{data.get('dateCreated', '')}"
        message_id = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return IncomingMessage(
        str(message_id), str(chat_id), str(sender), text.strip(), _has_image_attachment(data)
    )


# Filler people put before addressing the bot: "hey schefter ...".
_GREETING = r"(?:hey|hi|hello|yo|ay|aye|ok|okay|um|uh|so|@)"
# A request opens one of these ways, or carries a "?". Auxiliaries (is, does,
# can, did) are deliberately absent: mid-sentence they are far more often
# statements about the bot ("we think schefter is offline") than questions to it.
# A real question with one almost always has the "?" anyway.
_ASKING = (
    r"(?:who|what|whats|when|where|why|how|which|whose|tell|show|give|make|create|post|start|"
    r"find|get|list|explain|rank|compare|set|run|check|send|settle|pick|draft|help|thoughts|"
    r"opinion|predict|project)"
)


def _is_request(text: str) -> bool:
    """Does this read as asking the bot for something, rather than about it?"""
    stripped = text.strip()
    if not stripped:
        return False
    if "?" in stripped:
        return True
    first = re.match(r"[a-z']+", stripped.casefold())
    return bool(first and re.fullmatch(_ASKING, first.group()))


def invoked_question(text: str) -> str | None:
    """The question, if this message asks the bot for something.

    The name is matched anywhere, since people write "Hey schefter who's
    projected to win?" as readily as they lead with it. But merely naming
    the bot is not addressing it: people may discuss
    it ("has everybody saved schefter as a contact", "according to schefter"),
    and answering those would make it a nuisance. So a mention only counts
    when a request is actually attached to it.
    """
    trigger = config.AGENT_TRIGGER.strip()
    if not trigger:
        return None
    escaped = re.escape(trigger)

    # Talking about the bot in the third person, never to it.
    about = rf"\b{escaped}(?:'s|’s|s')|\b(?:the|a|that|this|his|its|their)\s+@?{escaped}\b"
    if re.search(about, text, flags=re.IGNORECASE):
        return None

    match = re.search(rf"@?\b{escaped}\b\s*[:,\-]?\s*", text, flags=re.IGNORECASE)
    if not match:
        return None

    before = text[:match.start()].strip()
    after = text[match.end():].strip()

    # Addressed directly at the front ("Schefter, latest moves"), optionally
    # after a greeting. Anything following is the request, command or not.
    if re.fullmatch(rf"(?:{_GREETING}[\s,!]*)*", before, flags=re.IGNORECASE):
        return after

    # Name last ("what do you think schefter?"): the request came before it.
    if not re.search(r"\w", after):
        return before if _is_request(text) else None

    # Name in the middle: only ours if what follows it is the ask.
    return after if _is_request(after) else None


def process(payload: dict) -> str:
    message = parse_event(payload)
    if message is None:
        return "ignored-event"
    if message.chat_id != config.CHAT_ID:
        return "ignored-chat"
    question = invoked_question(message.text)
    if question is None:
        # Bare "2" while a poll is open is a vote. Recorded silently: one
        # confirmation per voter would flood a 14-person chat.
        vote = polls.parse_vote(message.text)
        if vote is not None:
            if not agent_state.claim(message.message_id):
                return "ignored-duplicate"
            polls.record_vote(message.sender, vote)
            return "recorded-vote"
        trade_reply = trades.bare_response(message.sender, message.text)
        if trade_reply is None:
            return "ignored-no-trigger"
        if not agent_state.claim(message.message_id):
            return "ignored-duplicate"
        imessage.send(trade_reply, message.chat_id)
        return "replied-trade"
    if not agent_state.claim(message.message_id):
        return "ignored-duplicate"

    if moderation.contains_slur(message.text):
        imessage.send(moderation.DECLINE_MESSAGE, message.chat_id)
        log(f"Declined message from {message.sender} (slur filter)")  # content never logged
        return "declined-slur"

    if message.has_image:
        imessage.send(IMAGE_DECLINE_MESSAGE, message.chat_id)
        log(f"Declined image from {message.sender}")
        return "declined-image"

    log(f"Question from {message.sender}: {question or '(help)'}")
    try:
        reply = agent.answer(question, agent_state.history(message.chat_id), actor=message.sender)
    except agent.AgentError as exc:
        log(f"ERROR answering: {exc}")
        reply = "I hit a snag pulling that report. The front office has been notified. Try me again in a minute."
    imessage.send(reply, message.chat_id)
    # A refusal in the history teaches the model to refuse the next question,
    # so only real answers become context.
    if not guardrails.is_refusal(reply):
        agent_state.append_exchange(message.chat_id, message.sender, question, reply)
    log(f"Replied to {message.sender}")
    return "replied"


class Worker:
    def __init__(self):
        self.items: queue.Queue[dict] = queue.Queue(maxsize=100)
        self.thread = threading.Thread(target=self._run, name="schefter-agent", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def submit(self, payload: dict) -> bool:
        try:
            self.items.put_nowait(payload)
            return True
        except queue.Full:
            return False

    def _run(self) -> None:
        while True:
            payload = self.items.get()
            try:
                process(payload)
            except Exception as exc:
                log(f"ERROR processing webhook: {type(exc).__name__}: {exc}")
            finally:
                self.items.task_done()


def handler(worker: Worker):
    class WebhookHandler(BaseHTTPRequestHandler):
        def _reply(self, status: int, body: str) -> None:
            encoded = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/health":
                self._reply(200, "ok")
            elif path == "/status":
                self._reply(200, json.dumps({
                    "started_at": STARTED_AT,
                    "loaded_source": LOADED_SOURCE,
                    "root": str(config.ROOT),
                }))
            else:
                self._reply(404, "not found")

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/webhook":
                return self._reply(404, "not found")
            provided = parse_qs(parsed.query).get("token", [""])[0]
            if not hmac.compare_digest(provided, config.AGENT_WEBHOOK_SECRET):
                return self._reply(401, "unauthorized")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("invalid content length")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("JSON body must be an object")
            except (ValueError, json.JSONDecodeError):
                return self._reply(400, "invalid JSON")
            if not worker.submit(payload):
                return self._reply(503, "queue full")
            self._reply(202, "accepted")

        def log_message(self, format, *args):
            return

    return WebhookHandler


def validate_config() -> list[str]:
    errors = []
    if not config.AGENT_ENABLED:
        errors.append("AGENT_ENABLED is not set to 1")
    if not config.CHAT_ID:
        errors.append("IMESSAGE_CHAT_ID is not set")
    if not config.AGENT_WEBHOOK_SECRET:
        errors.append("AGENT_WEBHOOK_SECRET is not set")
    if not config.AGENT_TRIGGER:
        errors.append("AGENT_TRIGGER is empty")
    if config.TRADE_ENABLED and len(config.TRADE_MANAGERS) < 2:
        errors.append("TRADE_ENABLED requires at least two entries in TRADE_MANAGERS")
    if config.TRADE_EXECUTION_PROVIDER not in ("none", "espn", "webhook"):
        errors.append("TRADE_EXECUTION_PROVIDER must be none, espn, or webhook")
    if config.TRADE_EXECUTION_PROVIDER == "webhook" and (
        not config.TRADE_EXECUTION_WEBHOOK_URL.lower().startswith("https://")
        or not config.TRADE_EXECUTION_SECRET
    ):
        errors.append("trade execution requires an HTTPS webhook URL and TRADE_EXECUTION_SECRET")
    if config.TRADE_EXECUTION_PROVIDER == "espn" and not config.ESPN_TRADE_WRITE_ENABLED:
        errors.append("ESPN execution requires ESPN_TRADE_WRITE_ENABLED=1")
    if config.TRADE_EXECUTION_PROVIDER == "espn" and config.ESPN_TRADE_AUTH_MODE not in (
        "league_manager", "team_credentials"
    ):
        errors.append("ESPN_TRADE_AUTH_MODE must be league_manager or team_credentials")
    if not config.AGENT_HOST in ("127.0.0.1", "localhost", "::1"):
        errors.append("AGENT_HOST must be loopback unless the listener is hardened separately")
    return errors


def main() -> int:
    errors = validate_config()
    if errors:
        for error in errors:
            log(f"CONFIG ERROR: {error}")
        return 2
    worker = Worker()
    worker.start()
    server = ThreadingHTTPServer((config.AGENT_HOST, config.AGENT_PORT), handler(worker))
    log(f"Listening on http://{config.AGENT_HOST}:{config.AGENT_PORT}/webhook")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
