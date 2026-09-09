"""Shared output cleanup for the bot's terse NFL-news voice."""
import re


_AI_OPENERS = re.compile(
    r"^\s*(?:(?:absolutely[.!,:]?|great question[.!,:]?|"
    r"here(?:'s| is) (?:the|a) (?:breakdown|quick breakdown)[.!:]?)\s*)+",
    re.IGNORECASE,
)

_MARKDOWN_LINK = re.compile(r"!?\[([^\]\n]+)\]\((https?://[^\s)]+)\)")
# DOTALL: a model happily wraps bold around a line break, and an unmatched
# marker must not survive into the chat.
_MARKDOWN_STRONG = re.compile(r"\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|__(.+?)__", re.DOTALL)
# Single-marker italics. The lookarounds keep snake_case identifiers and
# arithmetic intact: a marker touching a word character is not emphasis.
_MARKDOWN_EMPHASIS = re.compile(
    r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])"
    r"|(?<![\w_])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w_])"
)
_URL_TOKEN = re.compile(r"https?://[^\s)]+", re.IGNORECASE)
_MARKDOWN_CODE = re.compile(r"`([^`\n]+)`")
_MARKDOWN_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s+")
_MARKDOWN_BULLET = re.compile(r"(?m)^(\s*)[*+]\s+")
# Whatever is left is an unclosed marker, usually from a reply truncated at
# AGENT_MAX_REPLY_CHARS mid-emphasis. A literal ** is never wanted in a text.
_ORPHAN_MARKER = re.compile(r"\*\*+|__+")


def _uppercase_emphasis(match: re.Match) -> str:
    """Uppercase emphasized prose without changing case-sensitive URL paths."""
    value = next(group for group in match.groups() if group is not None)
    pieces = _URL_TOKEN.split(value)
    urls = _URL_TOKEN.findall(value)
    result = []
    for index, piece in enumerate(pieces):
        result.append(piece.upper())
        if index < len(urls):
            result.append(urls[index])
    return "".join(result)


def _strip_emphasis(match: re.Match) -> str:
    return next(group for group in match.groups() if group is not None)


def polish(text: str) -> str:
    """Make model output readable in Messages, which does not render Markdown."""
    cleaned = _AI_OPENERS.sub("", text.strip())
    # Apple Messages receives plain text through AppleScript. Preserve a link's
    # label and URL, and translate intended emphasis into readable plain text.
    # imessage.py later isolates URLs so Messages can build rich link previews.
    cleaned = _MARKDOWN_LINK.sub(lambda match: f"{match.group(1)} ({match.group(2)})", cleaned)
    cleaned = _MARKDOWN_STRONG.sub(_uppercase_emphasis, cleaned)
    cleaned = _MARKDOWN_EMPHASIS.sub(_strip_emphasis, cleaned)
    cleaned = _MARKDOWN_CODE.sub(r"\1", cleaned)
    cleaned = _MARKDOWN_HEADING.sub("", cleaned)
    cleaned = _MARKDOWN_BULLET.sub(r"\1- ", cleaned)
    cleaned = _ORPHAN_MARKER.sub("", cleaned)
    cleaned = re.sub(r"[ \t]*\u2014[ \t]*", ", ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()
