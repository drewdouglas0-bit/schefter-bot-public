# Security and privacy

This is a self-hosted hobby project, not a security-audited messaging service.

## Before running it

- Tell group members that the bot processes their messages. Use a dedicated
  bot identity clearly labeled "Schefter Bot" and scope it to one configured chat.
- Keep `.env`, ESPN session cookies, OpenAI keys, webhook secrets, chat GUIDs,
  sender mappings, logs, state files, and history databases private. Never attach
  them to GitHub issues. `.env.example` contains placeholders only.
- Use your own ESPN cookies. These grant account access; treat them as passwords.
  Store any per-team trade credentials outside the checkout with restrictive
  filesystem permissions.
- Keep the listener bound to `127.0.0.1` with a strong random webhook secret.
  Do not expose the local webhook through a public tunnel without a separate
  security review. URLs containing its token should not be shared or logged publicly.
- Interactive requests, recent conversation context, and league data used to
  answer them may be sent to OpenAI. Current-news queries may use web search.
  BlueBubbles also has access to the Messages account. Review provider policies
  and group consent before enabling these integrations.
- Conversation state and league history are persisted locally. Review the paths
  in `schefter/config.py`, restrict access to the macOS account, and include these
  files in your own retention/deletion plan.
- Trade execution is disabled by default. Enabling it can change real ESPN
  rosters. Use only with the relevant managers' permission and verify outcomes.
  Prompt checks and consent gates are safeguards, not a guarantee against abuse.

## Reporting an issue

Use GitHub's private vulnerability reporting option if available on this repo.
Do not publish credentials, personal addresses, real chat content, or an exploit
against a running installation in a public issue. Revoke or rotate an exposed
credential at its provider; deleting a GitHub file does not revoke the credential.

The initial public release uses a sanitized snapshot with fresh commit history.
Secret scanning reduces accidental exposure but cannot guarantee that every kind
of private information will be detected.
