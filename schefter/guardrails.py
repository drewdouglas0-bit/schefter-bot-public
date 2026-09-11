"""Deterministic guardrails applied before the conversational model gets tools.

Cherry-picked from feature/schefter-voice-guardrails — just the local,
non-LLM checks (prompt-injection/secret-exfiltration patterns, a question
length cap, and trade-tool authorization). The football-only scope check
lives directly in agent.py's SYSTEM_PROMPT instead of a separate classifier
call here, to keep answering a question a single API round trip.
"""
import re


SECURITY_REPLY = (
    "I can't help reveal or bypass the bot's private instructions, credentials, or files."
)
TOO_LONG_REPLY = "That's too much tape for one message. Send a shorter football question."
TRADE_CREATE_AUTH_REPLY = (
    "I didn't create anything. To make an offer, give me a direct command like "
    "“Offer Team Two Player A for Player B.”"
)
TRADE_RESPONSE_AUTH_REPLY = (
    "I didn't change that trade. Reply with a direct command such as “Accept trade ab12cd34” "
    "or “Reject trade ab12cd34.”"
)
POLL_CREATE_AUTH_REPLY = (
    "I didn't post a poll. Ask directly, such as “Set a poll for PPR, half PPR, or no PPR,” "
    "or tag me with a choice question containing at least two options."
)

_SECURITY_PATTERNS = (
    re.compile(
        r"\b(?:system prompt|developer (?:message|prompt)|hidden instructions?|api keys?)\b|"
        r"(?:^|\s)\.env\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:ignore|disregard|override|bypass|forget)\b.{0,100}"
        r"\b(?:instructions?|prompts?|rules?|guardrails?|polic(?:y|ies))\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:reveal|show|print|repeat|send|give|expose|leak|dump)\b.{0,100}"
        r"\b(?:system prompt|developer message|hidden instructions?|api keys?|passwords?|"
        r"credentials?|cookies?|environment variables?|\.env|secrets?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(?:open|read|list|search|inspect|download|upload)\b.{0,100}"
        r"\b(?:local files?|filesystem|\.env|private files?|source tree)\b",
        re.IGNORECASE | re.DOTALL,
    ),
)

_CREATE_TRADE_PATTERNS = (
    re.compile(r"^\s*(?:please\s+)?(?:offer|propose)\b", re.IGNORECASE),
    re.compile(
        r"^\s*(?:please\s+)?(?:create|send|submit|make)\s+"
        r"(?:a\s+|the\s+)?(?:trade|deal|offer)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:can|could|would|will)\s+you\s+(?:please\s+)?"
        r"(?:(?:offer|propose)\b|(?:create|send|submit|make)\s+"
        r"(?:a\s+|the\s+)?(?:trade|deal|offer)\b)",
        re.IGNORECASE,
    ),
)
_RESPOND_TRADE_PATTERN = re.compile(
    r"^\s*(?:(?:yes|no)|(?:i\s+)?(?:accept|reject|decline)"
    r"(?:\s+(?:it|that|[a-f0-9]{8}|(?:the\s+)?(?:trade|deal|offer|proposal)\b.*))?)"
    r"[.!]?\s*$",
    re.IGNORECASE,
)
_CREATE_POLL_PATTERNS = (
    re.compile(
        r"^\s*(?:please\s+)?(?:create|send|start|make|post|set(?:\s+up)?|run)\s+"
        r"(?:an?\s+|the\s+)?poll\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:can|could|would|will)\s+you\s+(?:please\s+)?"
        r"(?:create|send|start|make|post|set(?:\s+up)?|run)\s+(?:an?\s+|the\s+)?poll\b",
        re.IGNORECASE,
    ),
    # A direct choice question addressed to the group: "should we do X, Y, or Z?"
    re.compile(
        r"^\s*(?:(?:should\s+we)|(?:(?:which|what)\b[^?]{0,120}\bshould\s+we))"
        r"[^?]{0,880}\b(?:or|versus|vs\.?)\b[^?]+\?\s*$",
        re.IGNORECASE,
    ),
)


# Distinctive fragments of every canned decline, however it was produced: some
# come from here, some from listener/moderation, some from the model following
# the prompt (where voice.polish may have rewritten the punctuation).
_REFUSAL_MARKERS = (
    "unable to help with that",
    "view or edit photos",
    "reply to that request",
    "help reveal or bypass",
    "too much tape",
    "didn't create anything",
    "didn't post a poll",
    "didn't change that trade",
)


def is_refusal(reply: str) -> bool:
    """Is this a canned decline rather than a real answer?

    Worth knowing because a refusal left in the conversation history teaches
    the model to refuse the next question too: a "make up your mind" decline
    two turns earlier is what made it refuse a plain banter question.
    """
    lowered = " ".join(str(reply or "").split()).casefold().replace("’", "'")
    return any(marker in lowered for marker in _REFUSAL_MARKERS)


def local_rejection(question: str, max_chars: int) -> str | None:
    """Reject resource abuse and obvious attempts to cross trust boundaries."""
    if len(question) > max_chars:
        return TOO_LONG_REPLY
    if any(pattern.search(question) for pattern in _SECURITY_PATTERNS):
        return SECURITY_REPLY
    return None


def tool_authorized(question: str, tool_name: str) -> bool:
    """Require unmistakable current-turn consent before a state-changing tool."""
    if tool_name == "create_trade_proposal":
        return any(pattern.search(question) for pattern in _CREATE_TRADE_PATTERNS)
    if tool_name == "respond_to_trade":
        return bool(_RESPOND_TRADE_PATTERN.search(question))
    if tool_name == "create_poll":
        return any(pattern.search(question) for pattern in _CREATE_POLL_PATTERNS)
    return True


def tool_authorization_reply(tool_name: str) -> str:
    if tool_name == "create_trade_proposal":
        return TRADE_CREATE_AUTH_REPLY
    if tool_name == "create_poll":
        return POLL_CREATE_AUTH_REPLY
    return TRADE_RESPONSE_AUTH_REPLY
