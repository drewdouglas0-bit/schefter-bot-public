"""Local, pre-API content gate for slurs/hate speech.

Checked before the trigger-matched question ever reaches OpenAI — cheaper
than a model call and means the message never leaves this machine. Not a
model-based judgment call: a fixed word list, so behavior is deterministic
and nothing here depends on an LLM choosing to comply with an instruction.

This list is inherently incomplete — extend SLURS below as needed. Keep
entries lowercase; matching is case-insensitive with word boundaries so it
won't fire on substrings inside unrelated words.
"""
import re

DECLINE_MESSAGE = "I can't reply to that request."

# Deliberately terse and non-exhaustive — covers the most common severe
# slurs across major categories. Add more as they come up; false negatives
# here just mean the SYSTEM_PROMPT-level backstop in agent.py has to catch it.
SLURS = {
    "nigger", "nigga", "chink", "spic", "wetback", "gook", "kike", "faggot",
    "fag", "tranny", "retard", "retarded", "coon", "beaner", "paki",
    "towelhead", "sandnigger", "cripple", "dyke", "jap",
}

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in SLURS) + r")\b",
    re.IGNORECASE,
)


def contains_slur(text: str) -> bool:
    return bool(_PATTERN.search(text or ""))
