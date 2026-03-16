# NotifyBridge

Local notification intake and debugging platform for webhook, email, and syslog messages.

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

## Launch with Docker

Build and run the containerized setup:

```bash
docker compose up --build
```

The app will expose:

- Web UI on port `8000`
- SMTP on port `2525`
- Syslog UDP on port `5514`

## Run tests

Run the full test suite:

```bash
uv run pytest -q
```

Run a specific test file:

```bash
uv run pytest tests/test_api.py -q
```
