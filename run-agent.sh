#!/bin/bash
# Long-running BlueBubbles webhook listener managed by launchd.
cd "$(dirname "$0")" || exit 1

LOG="agent.log"
[ -f "$LOG" ] && [ "$(wc -c <"$LOG")" -gt 1000000 ] && mv "$LOG" "$LOG.1"

exec ./venv/bin/python -m schefter.listener >>"$LOG" 2>&1
