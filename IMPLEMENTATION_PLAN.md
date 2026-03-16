# NotifyBridge Implementation Checklist

- [x] Phase 1: Skeleton, packaging, and single-command local dev
- [x] Phase 2: SQLite schema and repository layer
- [x] Phase 3: Core domain services and normalization
- [x] Phase 4: Web API and management backend
- [x] Phase 5: Web UI for full management
- [x] Phase 6: Transport listeners
- [x] Phase 7: K9s-style read-only TUI
- [x] Phase 8: Dockerization and final launch polish

## Phase Notes

### Phase 1
- [x] Python package skeleton
- [x] Config loading
- [x] Runtime bootstrap
- [x] `notifybridge dev` CLI entrypoint
- [x] Structured logging buffer
- [x] Phase 1 unit tests passing

### Phase 2
- [x] SQLite schema
- [x] API key repository methods
- [x] Notification repository methods
- [x] Audit repository methods
- [x] Counts and deletion semantics
- [x] Phase 2 unit tests passing

### Phase 3
- [x] Shared ingestion service
- [x] Normalization helpers
- [x] Audit logging on all ingress attempts
- [x] Syslog strict/permissive routing
- [x] SSE event publishing hooks
- [x] Phase 3 unit tests passing

### Phase 4
- [x] HTTP routes for keys
- [x] HTTP routes for notifications
- [x] HTTP routes for audit log
- [x] SSE endpoint
- [x] Webhook ingestion route
- [x] Phase 4 unit tests passing

### Phase 5
- [x] Web UI shell
- [x] Theme toggle persistence
- [x] Key management UI
- [x] Notification and audit views
- [x] Phase 5 unit tests passing

### Phase 6
- [x] SMTP adapter
- [x] Syslog adapter
- [x] Transport-level tests
- [x] Phase 6 unit tests passing

### Phase 7
- [x] Textual TUI layout
- [x] TUI view models
- [x] Read-only operator workflow
- [x] Phase 7 unit tests passing

### Phase 8
- [x] Dockerfile
- [x] Docker Compose
- [x] Launch docs
- [x] Packaging smoke checks
- [x] Phase 8 unit tests passing
