"""Lists iMessage chats so you can grab your league group's GUID.

    python -m schefter.chats          # group chats only
    python -m schefter.chats --all    # every chat, including 1:1
"""
import subprocess
import sys

from . import config

LIST_SCRIPT = config.ROOT / "tools" / "list_chats.applescript"


def main() -> int:
    show_all = "--all" in sys.argv
    result = subprocess.run(
        ["osascript", str(LIST_SCRIPT)], capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        print("Could not read chats from Messages.app:", file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
        print(
            "\nGrant your terminal permission under System Settings > Privacy & "
            "Security > Automation > (your terminal) > Messages.",
            file=sys.stderr,
        )
        return 1

    rows = [line.split("\t") for line in result.stdout.splitlines() if line.strip()]
    if not show_all:
        # Group chats have GUIDs like "iMessage;+;chat123..."; 1:1 chats use ";-;".
        rows = [r for r in rows if ";+;" in r[0]]

    if not rows:
        print("No chats found. Open Messages.app and make sure it's signed in.")
        return 1

    for row in rows:
        guid = row[0]
        name = row[1] if len(row) > 1 else ""
        who = row[2] if len(row) > 2 else ""
        print(f"{guid}\n    name: {name}\n    members: {who}\n")

    print("Copy the matching GUID into .env as IMESSAGE_CHAT_ID=")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
