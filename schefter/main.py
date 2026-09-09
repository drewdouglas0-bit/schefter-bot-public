"""Polls the league and reports anything worth reporting to the group chat.

    python -m schefter.main                     # normal poll
    python -m schefter.main --dry-run           # print instead of send
    python -m schefter.main --only recap        # run one feature
    python -m schefter.main --force             # ignore schedule windows
    python -m schefter.main --reseed            # mark current activity seen
    python -m schefter.main --replay N          # print last N transactions

Preview a scheduled feature any time with:
    python -m schefter.main --only recap --force --dry-run

The draft lottery never runs on a schedule. Trigger it explicitly:
    python -m schefter.main --only draft_lottery --force --send
"""
import fcntl
import sys
import time
from datetime import datetime

from . import config, espn, features, formatter, imessage, state, voice

LOCK_FILE = config.ROOT / ".main.lock"


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def _replay(n: int) -> int:
    for a in sorted(espn.recent_activity(size=n), key=lambda a: a.date):
        msg = formatter.format_activity(a)
        when = datetime.fromtimestamp(a.date / 1000)
        print(f"\n--- {when:%a %b %d %I:%M %p} ---\n{msg or '(nothing to report)'}")
    return 0


def main() -> int:
    # Prevents overlapping runs (e.g. a prior invocation still hung on a slow
    # osascript call when the next scheduled poll fires) from both building
    # the same outbox and double-sending it.
    lock_fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("Another instance is already running — skipping this poll.")
        return 0

    args = sys.argv[1:]
    force = "--force" in args
    # --force skips the schedule windows, which makes it easy to double-post a
    # weekly message. So it previews by default; --send is the explicit opt-in.
    dry_run = (
        config.DRY_RUN
        or "--dry-run" in args
        or (force and "--send" not in args)
    )
    only = None
    if "--only" in args:
        i = args.index("--only")
        only = args[i + 1] if len(args) > i + 1 else None

    try:
        if "--replay" in args:
            i = args.index("--replay")
            return _replay(int(args[i + 1]) if len(args) > i + 1 else 10)
        lg = espn.get_league()
    except Exception as e:
        log(f"ERROR fetching from ESPN: {type(e).__name__}: {e}")
        return 1

    st = state.load()

    if "--reseed" in args:
        acts = espn.recent_activity()
        st["seen"] = [state.fingerprint(a) for a in acts]
        st["seeded"] = True
        state.save(st)
        log(f"Reseeded {len(st['seen'])} activities. Nothing sent.")
        return 0

    now = datetime.now(config.TZ)
    outbox = []

    for feature in features.ALL:
        if only and feature.NAME != only:
            continue
        if not feature.enabled(config):
            continue
        try:
            if not force and not feature.should_run(now, st, lg, config):
                continue
            msgs = feature.run(lg, st, config)
        except Exception as e:
            # One broken feature shouldn't take down the rest of the poll.
            log(f"ERROR in {feature.NAME}: {type(e).__name__}: {e}")
            continue
        if msgs:
            outbox.extend((feature.NAME, voice.polish(m)) for m in msgs)

    # A preview must never persist state. Otherwise dry-running the injury
    # feature would mark everything announced and the real alert never fires.
    if dry_run:
        for name, msg in outbox:
            print(f"\n--- [{name}] would send ---\n{msg}\n")
        log(f"Would send {len(outbox)} message(s). State unchanged.")
        return 0

    if not outbox:
        state.save(st)  # features may have advanced state without emitting
        log("Nothing to report.")
        return 0

    sent = 0
    # From here on every send is real; state is persisted after each one.
    # Catches every exception, not just SendError — a hung osascript call
    # (subprocess.TimeoutExpired) must not crash past this point uncaught,
    # or the in-memory dedup state built up above (e.g. injury statuses)
    # never reaches disk and every feature re-announces from scratch next poll.
    for name, msg in outbox:
        try:
            imessage.send(msg)
        except Exception as e:
            log(f"ERROR sending ({name}): {type(e).__name__}: {e}")
            state.save(st)
            return 1
        sent += 1
        state.save(st)  # persist as we go so a crash can't double-post
        time.sleep(2)   # let Messages settle between sends

    state.save(st)
    log(f"Sent {sent} message(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
