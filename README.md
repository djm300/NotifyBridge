# NotifyBridge

Local notification intake and debugging platform for webhook, email, and syslog messages.

## What it does

NotifyBridge runs four main pieces together:

- a primary web UI for API key management, notifications, demo actions, and audit log review
- a local webhook endpoint
- a local SMTP listener
- a local syslog listener

When launched from a terminal, it also opens a consultation-only Textual TUI with three panes for logs, keys, and incoming messages.

## Launch locally

Install dependencies and start the app:

```bash
uv sync --extra dev
uv run notifybridge dev
```

Default local endpoints:

- Web UI: `http://127.0.0.1:8000`
- SMTP: `127.0.0.1:2525`
- Syslog UDP: `127.0.0.1:5514`

## Operate the app

### 1. Open the web UI

Go to:

```text
http://127.0.0.1:8000
```

Use the web UI to:

- generate 20-character random API keys
- enable or disable API keys
- remove API keys
- filter the middle pane to one API key
- review per-key counts
- inspect notifications
- inspect the audit log
- mark messages as read
- delete one or many messages
- clear all messages for a key
- clear all notifications globally
- generate random localhost demo traffic

### 2. Watch the TUI

If launched from a real terminal, the Textual interface shows:

- left pane: live logs
- middle pane: API keys and counts
- right pane: incoming messages

The TUI is consultation-only in v1. Use the web UI for all mutating actions.

Slash commands in the TUI:

- `/q` or `/e`: exit the TUI

### 3. Send test traffic

First generate an API key in the web UI. NotifyBridge creates 20-character random alphanumeric keys. In the examples below, replace `YOUR_20_CHAR_KEY` with a real generated key.

#### Webhook example

```bash
curl -X POST http://127.0.0.1:8000/ingest/webhook/YOUR_20_CHAR_KEY \
  -H 'Content-Type: application/json' \
  -d '{"title":"Build complete","body":"nightly pipeline finished"}'
```

#### Email example

Send an email to:

```text
YOUR_20_CHAR_KEY@notifybridge.local
```

Only the primary `To:` address is used for authentication.
`CC:`, `BCC:`, and `Subject:` are ignored for API key auth.

If you want to test locally with a raw SMTP client:

```bash
nc 127.0.0.1 2525
```

Then send:

```text
EHLO localhost
MAIL FROM:<alerts@example.test>
RCPT TO:<YOUR_20_CHAR_KEY@notifybridge.local>
DATA
From: alerts@example.test
To: YOUR_20_CHAR_KEY@notifybridge.local
Subject: Disk warning

/var is above 85%
.
QUIT
```

#### Syslog examples

Preferred RFC 5424 structured-data auth:

```bash
echo '<134>1 2026-03-16T20:00:00Z app-01 notifybridge 1234 ID47 [notifybridge@32473 apiKey="YOUR_20_CHAR_KEY"] backup run failed' | nc -u 127.0.0.1 5514
```

Fallback prefix auth:

```bash
echo '<134>Mar 16 20:00:00 app-01 [nb:YOUR_20_CHAR_KEY] backup run failed' | nc -u 127.0.0.1 5514
```

If syslog permissive mode is enabled, syslog messages without an API key are accepted into the unassigned syslog bucket.

## Configuration

These environment variables are supported:

- `NOTIFYBRIDGE_SQLITE_PATH`
- `NOTIFYBRIDGE_HTTP_HOST`
- `NOTIFYBRIDGE_HTTP_PORT`
- `NOTIFYBRIDGE_SMTP_HOST`
- `NOTIFYBRIDGE_SMTP_PORT`
- `NOTIFYBRIDGE_SYSLOG_HOST`
- `NOTIFYBRIDGE_SYSLOG_PORT`
- `NOTIFYBRIDGE_SYSLOG_MODE`
- `NOTIFYBRIDGE_EMAIL_DOMAIN`
- `NOTIFYBRIDGE_THEME_DEFAULT`

Example:

```bash
NOTIFYBRIDGE_SYSLOG_MODE=permissive uv run notifybridge dev
```

## Launch with Docker

Build and run the containerized setup:

```bash
docker compose up --build
```

The app will expose:

- Web UI on port `8000`
- SMTP on port `2525`
- Syslog UDP on port `5514`

To stop it:

```bash
docker compose down
```

## Run tests

Run the full test suite:

```bash
uv run pytest -q
```

Run a specific test file:

```bash
uv run pytest tests/test_api.py -q
```

Useful test groups:

- ingestion logic: `uv run pytest tests/test_ingestion.py -q`
- API/backend: `uv run pytest tests/test_api.py -q`
- web UI shell: `uv run pytest tests/test_web_ui.py -q`
- transport adapters: `uv run pytest tests/test_transport_adapters.py -q`
- packaging checks: `uv run pytest tests/test_packaging.py -q`
