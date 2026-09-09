"""Adds, drops, waiver claims and trades: the original beat."""
from .. import formatter, state

NAME = "transactions"


def enabled(cfg):
    return cfg.FEATURES["transactions"]


def should_run(now, st, lg, cfg):
    return True  # event-driven; checked every poll


def run(lg, st, cfg):
    activities = sorted(lg.recent_activity(size=cfg.FETCH_SIZE), key=lambda a: a.date)
    seen = set(st["seen"])
    fresh = [a for a in activities if state.fingerprint(a) not in seen]

    # First run: record history without dumping it all into the chat.
    if not st.get("seeded"):
        st["seen"] = [state.fingerprint(a) for a in activities]
        st["seeded"] = True
        return []

    if not fresh:
        return []

    # Waiver processing and post-draft churn can dump a dozen at once.
    if len(fresh) > cfg.MAX_PER_POLL:
        st["seen"].extend(state.fingerprint(a) for a in fresh)
        return [formatter.format_digest(fresh)]

    messages = []
    for activity in fresh:
        msg = formatter.format_activity(activity)
        st["seen"].append(state.fingerprint(activity))
        if msg:
            messages.append(msg)
    return messages
