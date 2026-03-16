# NotifyBridge Security Review

Implementation review date: 2026-03-16

Scope reviewed:

- `src/notifybridge/api/routes.py`
- `src/notifybridge/static/app.js`
- `src/notifybridge/core/ingestion.py`
- `src/notifybridge/core/normalization.py`
- `src/notifybridge/ingress/email.py`
- `src/notifybridge/ingress/syslog.py`
- `src/notifybridge/config.py`
- `src/notifybridge/storage/repository.py`

## Bottom Line

For local-only use, the current implementation is workable.

For public Internet exposure, it is not hardened. Opportunistic scanners, spam bots, and hostile payloads would cause problems quickly. The highest-risk issues are:

- stored XSS in the web UI
- completely unauthenticated management and data APIs
- full request/body parsing before size checks or auth gates
- unlimited audit and notification payload storage
- SMTP and syslog paths that accept and process arbitrary input with no rate, size, or retention controls

The main practical risk is denial of service and operator compromise through the browser, not classic Python stack-buffer overflow.

## Findings

### 1. Stored XSS in the UI via `innerHTML`

Risk: high

Relevant code:

- `src/notifybridge/static/app.js:33`
- `src/notifybridge/static/app.js:49`
- `src/notifybridge/static/app.js:57`

The UI renders untrusted fields directly into HTML using template strings and `innerHTML`:

- API key names
- notification titles
- notification bodies
- audit summaries

Any inbound webhook, email subject/body, syslog message, or even malicious API key name can become executable markup in the operator's browser.

Examples:

- webhook body: `<img src=x onerror=alert(1)>`
- email subject containing HTML event handlers
- syslog line with embedded markup
- API key created as `<svg onload=alert(1)>`

Impact:

- arbitrary JavaScript in the operator session
- full visibility into notifications and audit data
- unauthorized API calls from the browser against the local instance

Required improvement:

- stop using `innerHTML` for untrusted data
- build DOM nodes and assign `.textContent`
- add a restrictive Content Security Policy in HTTP responses

### 2. All management and data APIs are unauthenticated

Risk: high

Relevant code:

- `src/notifybridge/api/routes.py:43`
- `src/notifybridge/api/routes.py:63`
- `src/notifybridge/api/routes.py:75`
- `src/notifybridge/api/routes.py:83`
- `src/notifybridge/api/routes.py:99`
- `src/notifybridge/api/routes.py:109`
- `src/notifybridge/api/routes.py:117`
- `src/notifybridge/api/routes.py:129`
- `src/notifybridge/api/routes.py:137`
- `src/notifybridge/api/routes.py:159`

There is no authentication or authorization on:

- listing keys
- creating and deleting keys
- listing notifications and audit entries
- marking messages read
- deleting messages
- clearing all notifications for a key
- subscribing to the event stream

If the HTTP server is reachable from the network, anyone can:

- enumerate configured API keys
- read all captured content
- delete or alter stored state
- add their own API keys and inject traffic into them

This is acceptable only if the service remains strictly localhost-bound. It is not acceptable for public exposure.

Required improvement:

- keep HTTP bound to `127.0.0.1` by default
- if remote access is needed, put the app behind an authenticated reverse proxy
- split ingestion auth from operator/admin auth

### 3. Webhook request bodies are fully parsed before auth or size limits

Risk: high

Relevant code:

- `src/notifybridge/api/routes.py:152`
- `src/notifybridge/api/routes.py:154`
- `src/notifybridge/core/ingestion.py:23`

`/ingest/webhook/{api_key}` performs `await request.json()` before calling the ingestion service. That means an attacker with an unknown key can still force:

- full request body read
- JSON decoding work
- memory growth proportional to payload size

This defeats the design goal of rejecting unknown keys before non-essential parsing.

Required improvement:

- validate the path key before reading/parsing the full body
- enforce a maximum content length
- reject unsupported content types without parsing
- stream or cap body reads

### 4. SMTP parsing is unbounded and accepts everything with `250`

Risk: high

Relevant code:

- `src/notifybridge/ingress/email.py:10`
- `src/notifybridge/ingress/email.py:11`
- `src/notifybridge/core/normalization.py:36`
- `src/notifybridge/core/ingestion.py:56`

The SMTP handler hands the full raw message to the parser and always returns `"250 Message accepted"`, even when the email is rejected at the application level.

Practical consequences on an Internet-exposed host:

- the service becomes a spam sink
- bots can fill SQLite with rejected-message audit entries
- large or deeply nested MIME messages can consume CPU and memory
- attachment-heavy messages are still parsed into memory before being "stripped"

The current code has no visible limits on:

- total SMTP message size
- header count/length
- MIME part count
- nesting depth
- decoded expansion

Required improvement:

- reject oversized mail during SMTP transaction handling
- return a reject status for clearly invalid or oversized inputs
- cap MIME complexity before full parse
- bound audit payload size for rejected mail

### 5. Syslog path has no size or rate controls and spawns unbounded tasks

Risk: medium-high

Relevant code:

- `src/notifybridge/ingress/syslog.py:12`
- `src/notifybridge/ingress/syslog.py:13`
- `src/notifybridge/ingress/syslog.py:14`

Every datagram results in:

- UTF-8 decode of the full payload
- task creation with `asyncio.create_task`
- downstream SQLite writes for accepted or rejected traffic

There is no visible limit on datagram size, arrival rate, or number of outstanding ingestion tasks. A burst of UDP garbage can create task pressure and storage churn very quickly.

This is particularly bad if permissive syslog mode is enabled, because unauthenticated Internet noise becomes stored notifications.

Required improvement:

- bound syslog frame length
- drop or sample excess traffic
- use a bounded queue instead of creating a task per packet
- forbid permissive syslog on non-local binds

### 6. Raw payload retention is unlimited and easy to abuse

Risk: medium-high

Relevant code:

- `src/notifybridge/core/ingestion.py:30`
- `src/notifybridge/core/ingestion.py:64`
- `src/notifybridge/core/ingestion.py:101`
- `src/notifybridge/storage/repository.py:65`
- `src/notifybridge/storage/repository.py:96`
- `src/notifybridge/storage/schema.py:16`
- `src/notifybridge/storage/schema.py:27`

Notifications and audit entries store full raw payloads as `TEXT` with no pruning, truncation, retention, or quota logic.

An attacker does not need code execution to win here. Repeated oversized requests, spam mail, or syslog floods can turn this into:

- disk exhaustion
- oversized SQLite growth
- degraded UI/API performance when listing data

Required improvement:

- store bounded excerpts by default
- cap record count and total database size
- add pruning/retention policies
- separate full-payload retention behind an explicit local-debug setting

### 7. API key values are operator-controlled and can become attack payloads

Risk: medium

Relevant code:

- `src/notifybridge/api/routes.py:65`
- `src/notifybridge/api/routes.py:66`
- `src/notifybridge/storage/repository.py:33`
- `src/notifybridge/static/app.js:35`

`POST /api/keys` accepts any non-empty trimmed string as an API key. There is no format restriction, length limit, or entropy requirement.

That creates multiple problems:

- XSS through rendered key names in the UI
- path abuse or awkward routing with slash-like or control characters
- weak, guessable keys if operators use names like `team-red`
- key disclosure because the secret is also used as the user-facing label

Required improvement:

- separate display name from secret key
- require random high-entropy secrets
- validate allowed character set and length
- never render secret material directly into the UI

### 8. No response hardening headers are set

Risk: medium

Relevant code:

- `src/notifybridge/api/app.py:10`
- `src/notifybridge/api/routes.py:33`

The app does not set visible browser hardening headers such as:

- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- `Cache-Control` for sensitive API data where appropriate

Because there is already a stored-XSS path, the missing CSP matters more than it otherwise would.

Required improvement:

- add CSP at the FastAPI layer or reverse proxy
- add basic response hardening headers

### 9. Rejected email and webhook inputs still do expensive string expansion

Risk: medium

Relevant code:

- `src/notifybridge/core/ingestion.py:30`
- `src/notifybridge/core/ingestion.py:64`

Rejected inputs are still converted to full strings for audit logging:

- `str(payload)` for unknown-key webhooks
- `raw_message.decode(..., errors="replace")` for rejected email

This means unknown-key traffic can still allocate large Python strings and write them to disk.

Required improvement:

- record only bounded excerpts for rejected traffic
- compute excerpts without full decode where possible
- enforce transport-level size caps before reaching these code paths

### 10. Email parsing surface is broader than the auth check requires

Risk: medium

Relevant code:

- `src/notifybridge/core/normalization.py:23`
- `src/notifybridge/core/normalization.py:37`
- `src/notifybridge/core/ingestion.py:57`

The code correctly uses header parsing to extract the auth candidate first, which is good. But for accepted mail it then fully parses the message with `BytesParser(...).parsebytes(raw_message)` and walks all parts.

That does not create classic Python buffer-overrun risk by itself, but it does create:

- parser complexity risk
- memory pressure risk
- exposure to bugs in library code and any native components it depends on

Required improvement:

- set explicit message-size and part-count limits
- treat attachment and multipart parsing as a constrained subsystem
- consider isolating mail parsing if the product ever accepts remote/public traffic

## Notes On The Stated Threat Model

### "Local execution through string formatting issues"

I did not find direct `eval`, `exec`, `os.system`, `shell=True`, or SQL string concatenation in the current implementation.

That is the good news.

The actual execution path today is browser-side, not local Python-side:

- hostile input is stored
- the frontend injects it into the DOM with `innerHTML`
- the operator opens the UI
- the payload executes in the browser context

So the current "string formatting" issue is a stored XSS issue, not shell injection.

### "Overrunning buffers"

I did not find obvious native-memory-unsafe code in the repository.

In pure Python, classic stack/heap buffer overrun risk is much lower than in C/C++. The realistic memory-safety concern here is:

- large or pathological inputs causing parser or allocator stress
- bugs in dependency/native layers
- unbounded payload retention exhausting RAM or disk

The hot spots are:

- JSON request parsing in FastAPI
- email parsing in the stdlib
- SQLite storage growth
- unbounded syslog task creation

## What To Fix First

1. Replace all `innerHTML` rendering of untrusted data with safe DOM construction using `textContent`.
2. Keep the service localhost-only unless it is behind an authenticated reverse proxy.
3. Add strict per-transport size limits before full parse or storage.
4. Add retention caps and raw-payload truncation for both notifications and audit entries.
5. Restrict API key format and separate display labels from actual secrets.
6. Add backpressure or bounded queues for syslog ingestion.
7. Add browser hardening headers, especially CSP.

## Verification Note

Tests were available and passed with:

```bash
uv run pytest -q
```

Passing tests here only show expected behavior, not security hardening. The issues above are design and implementation exposure gaps rather than test regressions.
