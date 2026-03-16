# NotifyBridge Security Notes

## Bottom Line

In its current intended shape, NotifyBridge is a local debugging tool, not a hardened public Internet service.

If you host it directly on the public Internet without additional controls, opportunistic scanners, spam bots, and input-fuzzing traffic will find it quickly and will likely cause one or more of these problems:

- SMTP spam flood and disk growth
- Webhook path brute-forcing against API keys
- Syslog noise and log flooding
- UI exposure of hostile payloads
- Resource exhaustion from oversized or deeply nested inputs

The main risk is not classic buffer overflow in pure Python application code. The bigger practical risks are:

- denial of service through unbounded request/body sizes
- dangerous parsing behavior in libraries or native extensions
- injection into logs, templates, terminals, or shell commands
- browser-side XSS if raw payloads are rendered unsafely

## Threat Model

Assume an Internet-exposed instance will receive:

- random HTTP probes for common paths and admin panels
- SMTP spam, malformed MIME, and attachment abuse
- malformed syslog frames and high-rate UDP/TCP garbage
- deliberately huge bodies intended to exhaust RAM, CPU, SQLite, or disk
- payloads containing HTML, JavaScript, ANSI escapes, format placeholders, and path-like strings

Threats explicitly in scope for this review:

- local execution through string formatting issues
- buffer or memory overruns in parser dependencies or native code
- service degradation from scanners and unauthenticated traffic

## Priority Findings

### 1. Public exposure should be treated as unsafe by default

The spec already says Internet hardening is a non-goal for v1. That is the correct default.

Required improvement:

- Bind listeners to `127.0.0.1` by default, not `0.0.0.0`
- Make public bind an explicit opt-in with a warning in config and UI
- Document that direct Internet exposure is unsupported without a reverse proxy and filtering

### 2. API keys in URL paths are guessable and leak easily

`POST /ingest/webhook/<api_key>` is simple, but path-based secrets leak into:

- access logs
- browser history and proxy logs
- metrics labels if carelessly instrumented

Required improvement:

- Use high-entropy keys, not human-readable names like `team-red`, for authentication
- Keep display names separate from secrets
- Redact path secrets in logs and audit records
- Prefer a header-based auth option if this ever moves beyond local use

### 3. Raw payload viewing creates an XSS hazard

The UI requirement to display raw payloads is a major risk if hostile HTML is rendered into the page.

Required improvement:

- Render all raw payloads as escaped text, never as HTML
- Forbid `innerHTML`-style rendering of message bodies and audit excerpts
- Serve with a strict Content Security Policy
- Treat email HTML parts as inert text unless sanitized by a proven sanitizer

If this is missed, a single inbound message can execute script in the operator’s browser.

### 4. Unbounded payload size will let scanners and spammers win

The fastest route to failure is letting HTTP, SMTP, or syslog inputs consume arbitrary memory, CPU, or disk.

Required improvement:

- Set hard maximum sizes per transport before deep parsing
- Reject or truncate oversized bodies early
- Cap header count, line length, MIME part count, attachment count, and syslog frame length
- Put quotas on audit log growth and notification retention
- Apply backpressure and connection timeouts

Minimum design rule:

- never call full-body reads on untrusted input without a size limit

### 5. SMTP and MIME parsing are a high-risk parser surface

SMTP is one of the most abuse-prone inputs here. Even in Python, parser bugs or pathological MIME trees can cause resource exhaustion.

Required improvement:

- Strip attachments without decoding arbitrarily large blobs into memory
- Limit MIME nesting depth and total part count
- Reject compressed or encoded content beyond a bounded expansion ratio
- Run SMTP parsing in a constrained worker process if possible

### 6. Syslog permissive mode is an abuse magnet

Permissive syslog mode means unauthenticated traffic can become stored data. On a public host, that becomes a free write endpoint for Internet noise.

Required improvement:

- Keep permissive mode disabled by default
- Disable it entirely when bound to non-local addresses
- Add source IP allowlists for syslog if remote ingestion is needed
- Rate-limit and cap storage for the unassigned bucket

### 7. Audit logging can become a second vulnerability

Logging hostile payloads is useful, but audit logs can still become:

- a disk exhaustion vector
- a secret leakage vector
- a terminal escape vector when viewed in CLI tools

Required improvement:

- store bounded excerpts by default, not unlimited raw payloads
- escape control characters on display
- redact likely secrets and auth material where feasible
- rotate and cap SQLite or associated log storage

## String Formatting and Local Execution Risks

Python does not have C-style stack buffer overflows in normal string handling, but unsafe string use can still lead to code execution or command execution.

Do not do the following with untrusted fields from webhook, email, syslog, or audit data:

- pass them into `eval`, `exec`, or dynamic imports
- interpolate them into shell commands
- use them as format strings for logging or templating
- use them to build filesystem paths without normalization and containment checks

Implementation rules:

- Always pass external data as parameters, never executable template fragments
- Use subprocess argument arrays, never `shell=True`, if subprocesses are ever needed
- Use parameterized SQLite queries everywhere
- Keep Jinja or other template engines in autoescape mode
- Never use user-controlled strings as the template itself

Examples of patterns to avoid:

```python
logger.info(payload)  # bad if downstream logging treats % sequences specially
os.system(f"mail-parser {subject}")  # command injection
html = f"<div>{raw_payload}</div>"  # XSS
query = f"DELETE FROM notifications WHERE api_key = '{api_key}'"  # SQL injection
```

Safer direction:

```python
logger.info("received payload: %r", payload)
subprocess.run(["mail-parser", subject], check=True)
cursor.execute("DELETE FROM notifications WHERE api_key = ?", (api_key,))
```

## Buffer Overrun and Native-Library Risks

If the app stays in pure Python plus well-maintained libraries, classic memory corruption risk is lower, but not zero.

Risk sources:

- C extensions in email, HTTP, TLS, compression, or SQLite-adjacent packages
- reverse proxies or sidecars written in C/C++
- image, archive, or attachment parsing libraries

Required improvement:

- Keep dependencies minimal
- Prefer mature libraries with active security maintenance
- Pin versions and update regularly
- Avoid parsing archives, office docs, images, or rich attachments in v1
- Consider process isolation for high-risk parsers

If attachment support grows later, isolate it in a separate worker with:

- memory limits
- CPU limits
- temp directory isolation
- no shell execution

## Anti-Bot and Internet Exposure Controls

If public hosting is unavoidable, minimum controls should include:

- reverse proxy in front of the app
- IP-based rate limiting per transport
- connection count limits
- request body size limits
- SMTP tarpitting or upstream filtering
- fail2ban-style response only if it is operationally justified
- optional allowlists for webhook and syslog senders
- TLS terminated at the proxy

Recommended stance:

- webhook: public only behind a reverse proxy with rate limits
- SMTP: do not expose directly unless you want to operate a spam sink
- syslog: do not expose permissive mode publicly

## Secure Implementation Checklist

- Default bind address is localhost only
- Public bind requires explicit config opt-in
- API keys are random, long, and separately named for display
- Unknown keys are rejected before full payload parsing
- Per-transport size, time, and concurrency limits are enforced
- Raw payload rendering is HTML-escaped
- CSP is enabled on the UI
- SQLite queries are parameterized
- No `eval`, `exec`, or `shell=True` on untrusted input
- Attachment handling is disabled or tightly bounded
- Audit storage is size-limited and rotated/pruned
- Unassigned syslog bucket is disabled on public hosts
- Secrets are redacted in logs and UI where practical

## Recommended Spec Changes

These should be added to the spec before implementation:

1. State that the default bind address is localhost only.
2. Require per-transport maximum payload sizes and parsing depth limits.
3. Require random high-entropy API keys distinct from human-readable labels.
4. Require HTML escaping for raw payload and message rendering.
5. Forbid permissive syslog mode on non-local binds.
6. Require retention caps and pruning for notifications and audit entries.
7. Require parameterized SQL and prohibit shell execution on untrusted input.
8. State that attachment parsing remains disabled or strictly bounded in v1.

## Practical Answer To The Main Question

If you host the current design directly on the Internet, spam bots and scanners probably will get the better of you operationally even if they do not achieve code execution.

With strict size limits, localhost-by-default binding, escaped rendering, random secrets, disabled public permissive syslog, and a reverse proxy enforcing rate limits, the design becomes reasonable for controlled exposure. Without those controls, expect nuisance traffic, storage abuse, and UI-level injection attempts almost immediately.
