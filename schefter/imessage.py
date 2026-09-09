"""Sends messages through Messages.app via AppleScript."""
import re
import subprocess
from urllib.parse import unquote_plus, urlsplit, urlunsplit

from . import config, voice

SEND_SCRIPT = config.ROOT / "tools" / "send.applescript"


class SendError(RuntimeError):
    pass


_URL = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
_MARKDOWN_LINK = re.compile(r"!?\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
_TRAILING_URL_PUNCTUATION = ".,!?;:)]}"
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
}


def _clean_url(raw_url: str) -> str:
    """Remove prose punctuation and common tracking parameters from a URL."""
    url = raw_url.rstrip(_TRAILING_URL_PUNCTUATION)
    parts = urlsplit(url)
    query = []
    for pair in parts.query.split("&") if parts.query else []:
        key = unquote_plus(pair.partition("=")[0]).casefold()
        if not key.startswith("utm_") and key not in _TRACKING_QUERY_KEYS:
            query.append(pair)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(query), parts.fragment))


def message_parts(text: str) -> list[str]:
    """Return a plain-text body followed by isolated, preview-friendly URLs."""
    urls: list[str] = []

    def remember_url(raw_url: str) -> str:
        clean = _clean_url(raw_url)
        if clean and clean not in urls:
            urls.append(clean)
        return clean

    def replace_markdown_link(match: re.Match) -> str:
        remember_url(match.group(2))
        return match.group(1)

    def replace_url(match: re.Match) -> str:
        raw_url = match.group(0)
        trimmed_url = raw_url.rstrip(_TRAILING_URL_PUNCTUATION)
        trailing_punctuation = raw_url[len(trimmed_url):]
        clean = remember_url(raw_url)
        host = urlsplit(clean).netloc.removeprefix("www.")
        return host + trailing_punctuation

    without_markdown_links = _MARKDOWN_LINK.sub(replace_markdown_link, text)
    body = _URL.sub(replace_url, voice.polish(without_markdown_links))
    body = re.sub(r"\(\s*\)", "", body)
    body = re.sub(r"[ \t]+([,.;:!?])", r"\1", body)
    body = re.sub(r"[ \t]{2,}", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return ([body] if body else []) + urls


def send(text: str, chat_id: str | None = None) -> None:
    chat_id = chat_id or config.CHAT_ID
    if not chat_id:
        raise SendError("IMESSAGE_CHAT_ID is not set. Run `python -m schefter.chats`.")

    for part in message_parts(text):
        result = subprocess.run(
            ["osascript", str(SEND_SCRIPT), chat_id, part],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise SendError(result.stderr.strip() or "osascript failed")
