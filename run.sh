#!/bin/bash
# Entry point for launchd. Keeps logs bounded so this can run all season.
cd "$(dirname "$0")" || exit 1

LOG="schefter.log"
[ -f "$LOG" ] && [ "$(wc -c <"$LOG")" -gt 1000000 ] && mv "$LOG" "$LOG.1"

./venv/bin/python -m schefter.main >>"$LOG" 2>&1
