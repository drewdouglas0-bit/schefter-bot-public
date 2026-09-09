"""Feature registry.

Each feature module exposes:
    NAME                              identifier, matches the config toggle
    enabled(cfg) -> bool              is it turned on
    should_run(now, st, lg, cfg)      is now the right moment
    run(lg, st, cfg) -> list[str]     messages to send (may mutate state)

Order matters: it's the order messages go out in a single poll.
"""
from . import draft_lottery, inactives, injuries, rankings, recap, rumors, transactions

ALL = [transactions, injuries, inactives, recap, rankings, rumors, draft_lottery]
BY_NAME = {m.NAME: m for m in ALL}
