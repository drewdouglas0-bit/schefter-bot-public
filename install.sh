#!/bin/bash
# One-shot setup: builds the venv, then generates and loads a launchd agent
# pointed at wherever this repo actually lives.
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

# Name the instance to run more than one league on this Mac:
#   INSTANCE=my-league ./install.sh
# launchd labels must be unique per instance. Without a name the labels stay
# exactly as they were, so an existing single-league install is untouched.
INSTANCE="${INSTANCE:-}"
if [ -n "$INSTANCE" ] && ! printf '%s' "$INSTANCE" | grep -Eq '^[a-z0-9][a-z0-9-]*$'; then
	echo "INSTANCE must be lowercase letters, digits, and dashes (got: $INSTANCE)" >&2
	exit 1
fi
SUFFIX="${INSTANCE:+.$INSTANCE}"

LABEL="com.schefterbot${SUFFIX}.agent"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LISTENER_LABEL="com.schefterbot${SUFFIX}.listener"
LISTENER_PLIST="$HOME/Library/LaunchAgents/$LISTENER_LABEL.plist"
INTERVAL="${POLL_INTERVAL:-300}"

echo "==> Installing schefter-bot from $DIR${INSTANCE:+ (instance: $INSTANCE)}"

if [ ! -d "$DIR/venv" ]; then
	echo "==> Creating virtualenv"
	python3 -m venv "$DIR/venv"
fi
"$DIR/venv/bin/pip" install --quiet --upgrade pip
"$DIR/venv/bin/pip" install --quiet -r "$DIR/requirements.txt"

if [ ! -f "$DIR/.env" ]; then
	cp "$DIR/.env.example" "$DIR/.env"
	chmod 600 "$DIR/.env"
	echo
	echo "==> Created .env — fill it in before the bot can run:"
	echo "    $DIR/.env"
	echo "    Then: $DIR/venv/bin/python -m schefter.doctor"
	exit 0
fi
chmod 600 "$DIR/.env"

mkdir -p "$HOME/Library/LaunchAgents"
cat >"$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>$DIR/run.sh</string>
	</array>
	<key>StartInterval</key>
	<integer>$INTERVAL</integer>
	<key>RunAtLoad</key>
	<false/>
	<key>StandardOutPath</key>
	<string>$DIR/launchd.out.log</string>
	<key>StandardErrorPath</key>
	<string>$DIR/launchd.err.log</string>
</dict>
</plist>
PLIST_EOF

chmod +x "$DIR/run.sh"
chmod +x "$DIR/run-agent.sh"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

cat >"$LISTENER_PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LISTENER_LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>$DIR/run-agent.sh</string>
	</array>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<true/>
	<key>ThrottleInterval</key>
	<integer>10</integer>
	<key>StandardOutPath</key>
	<string>$DIR/launchd-agent.out.log</string>
	<key>StandardErrorPath</key>
	<string>$DIR/launchd-agent.err.log</string>
</dict>
</plist>
PLIST_EOF

launchctl unload "$LISTENER_PLIST" 2>/dev/null || true
if grep -Eq '^[[:space:]]*AGENT_ENABLED=(1|true|yes|on)([[:space:]]*(#.*)?)$' "$DIR/.env"; then
	launchctl load "$LISTENER_PLIST"
	echo "==> Interactive agent '$LISTENER_LABEL' loaded on the configured local port"
else
	echo "==> Interactive agent disabled (set AGENT_ENABLED=1, then rerun ./install.sh)"
fi

echo "==> Agent '$LABEL' loaded, polling every ${INTERVAL}s"
echo "==> Verify:  $DIR/venv/bin/python -m schefter.doctor"
echo "==> Logs:    $DIR/schefter.log"
echo "==> Agent log: $DIR/agent.log"
echo "==> Stop:    launchctl unload $PLIST"
