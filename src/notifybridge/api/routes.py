from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from notifybridge.core.keys import generate_api_key
from notifybridge.core.models import Notification
from notifybridge.tui.demo import seed_random_demo


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def notification_to_dict(item: Notification) -> dict:
    """Serialize one notification for API responses.

    Inputs:
    - `item`: notification dataclass instance.

    Outputs:
    - Plain dictionary suitable for JSON encoding.
    """
    return asdict(item)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main web shell.

    Inputs:
    - `request`: FastAPI request carrying app state.

    Outputs:
    - HTML response for the browser UI.

    Why the decorator is used:
    - `@router.get` binds this function to an HTTP GET route and lets FastAPI
      handle request parsing and response serialization.
    """
    runtime = request.app.state.runtime
    return templates.TemplateResponse(
        request,
        "index.html",
        {"settings": runtime.settings},
    )


@router.get("/api/keys")
async def list_keys(request: Request):
    """Return configured API keys and count summaries.

    Inputs:
    - `request`: FastAPI request carrying app state.

    Outputs:
    - JSON payload containing per-key counts and unassigned syslog summary.

    Why the decorator is used:
    - `@router.get` exposes this read-only handler as an HTTP GET endpoint.
    """
    repo = request.app.state.runtime.repository
    return {
        "keys": [asdict(item) for item in repo.list_key_summaries()],
        "unassigned": {
            "enabled": repo.get_syslog_mode() == "permissive",
            "summary": asdict(repo.unassigned_summary()),
        },
    }


@router.post("/api/keys")
async def create_key(request: Request):
    """Create one API key from JSON request data.

    Inputs:
    - `request`: FastAPI request carrying app state. Request body is optional and ignored.

    Outputs:
    - `201` JSON response containing a generated 20-character API key.

    Why the decorator is used:
    - `@router.post` exposes this mutating handler as an HTTP POST endpoint.
    """
    api_key = generate_api_key(20)
    repo = request.app.state.runtime.repository
    repo.add_api_key(api_key)
    await request.app.state.runtime.event_bus.publish("keys.changed", {"api_key": api_key})
    return JSONResponse({"api_key": api_key}, status_code=201)


@router.delete("/api/keys/{api_key}")
async def delete_key(api_key: str, request: Request):
    """Delete one API key by path parameter.

    Inputs:
    - `api_key`: key string from the URL path.
    - `request`: FastAPI request carrying app state.

    Outputs:
    - JSON response confirming deletion.

    Why the decorator is used:
    - `@router.delete` exposes this destructive handler as an HTTP DELETE endpoint.
    """
    repo = request.app.state.runtime.repository
    repo.remove_api_key(api_key)
    await request.app.state.runtime.event_bus.publish("keys.changed", {"api_key": api_key})
    return {"deleted": api_key}


@router.post("/api/keys/{api_key}/enabled")
async def set_key_enabled(api_key: str, request: Request):
    """Enable or disable one API key.

    Inputs:
    - `api_key`: key string from the URL path.
    - `request`: JSON body with `enabled`.

    Outputs:
    - JSON acknowledgement with the updated enabled state.

    Why the decorator is used:
    - `@router.post` exposes this state-change handler as an HTTP endpoint.
    """
    payload = await request.json()
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail="enabled must be a boolean")
    repo = request.app.state.runtime.repository
    repo.set_api_key_enabled(api_key, enabled)
    await request.app.state.runtime.event_bus.publish("keys.changed", {"api_key": api_key, "enabled": enabled})
    return {"api_key": api_key, "enabled": enabled}


@router.get("/api/notifications")
async def list_notifications(request: Request, api_key: str | None = None, assignment_type: str | None = None):
    """List notifications with optional API key and assignment filters.

    Inputs:
    - `request`: FastAPI request carrying app state.
    - `api_key`: optional query filter.
    - `assignment_type`: optional query filter.

    Outputs:
    - JSON list of serialized notifications.

    Why the decorator is used:
    - `@router.get` exposes this read-only handler as an HTTP GET endpoint.
    """
    repo = request.app.state.runtime.repository
    items = repo.list_notifications(api_key=api_key, assignment_type=assignment_type)
    return {"items": [notification_to_dict(item) for item in items]}


@router.get("/api/notifications/{notification_id}")
async def get_notification(notification_id: int, request: Request):
    """Fetch one notification by ID.

    Inputs:
    - `notification_id`: path parameter.
    - `request`: FastAPI request carrying app state.

    Outputs:
    - JSON notification object or `404`.

    Why the decorator is used:
    - `@router.get` exposes this read-only handler as an HTTP GET endpoint.
    """
    repo = request.app.state.runtime.repository
    item = repo.get_notification(notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification_to_dict(item)


@router.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, request: Request):
    """Persist `read` state for one notification.

    Inputs:
    - `notification_id`: path parameter.
    - `request`: FastAPI request carrying app state.

    Outputs:
    - JSON acknowledgement with updated state or `404`.

    Why the decorator is used:
    - `@router.post` exposes this state-change handler as an HTTP endpoint.
    """
    repo = request.app.state.runtime.repository
    if not repo.get_notification(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    repo.mark_read(notification_id)
    await request.app.state.runtime.event_bus.publish("notification.updated", {"id": notification_id})
    return {"id": notification_id, "state": "read"}


@router.delete("/api/notifications/{notification_id}")
async def delete_notification(notification_id: int, request: Request):
    """Delete one notification by ID.

    Inputs:
    - `notification_id`: path parameter.
    - `request`: FastAPI request carrying app state.

    Outputs:
    - JSON acknowledgement naming the deleted ID.

    Why the decorator is used:
    - `@router.delete` exposes this destructive handler as an HTTP DELETE endpoint.
    """
    repo = request.app.state.runtime.repository
    repo.delete_notification(notification_id)
    await request.app.state.runtime.event_bus.publish("notification.deleted", {"id": notification_id})
    return {"deleted": notification_id}


@router.post("/api/notifications/bulk-delete")
async def bulk_delete_notifications(request: Request):
    """Delete multiple notifications by explicit ID list.

    Inputs:
    - `request`: JSON body with `ids: list[int]`.

    Outputs:
    - JSON acknowledgement listing deleted IDs or `400` for invalid payload.

    Why the decorator is used:
    - `@router.post` exposes this bulk mutation as an HTTP endpoint.
    """
    payload = await request.json()
    ids = payload.get("ids")
    if not isinstance(ids, list) or not all(isinstance(item, int) for item in ids):
        raise HTTPException(status_code=400, detail="ids must be a list of integers")
    repo = request.app.state.runtime.repository
    repo.bulk_delete_notifications(ids)
    await request.app.state.runtime.event_bus.publish("notifications.bulk_deleted", {"ids": ids})
    return {"deleted": ids}


@router.delete("/api/notifications/by-key/{api_key}")
async def clear_key_notifications(api_key: str, request: Request):
    """Delete all notifications assigned to one API key.

    Inputs:
    - `api_key`: key string from the URL path.
    - `request`: FastAPI request carrying app state.

    Outputs:
    - JSON acknowledgement naming the cleared key.

    Why the decorator is used:
    - `@router.delete` exposes this destructive handler as an HTTP DELETE endpoint.
    """
    repo = request.app.state.runtime.repository
    repo.clear_notifications_for_key(api_key)
    await request.app.state.runtime.event_bus.publish("notifications.cleared", {"api_key": api_key})
    return {"cleared": api_key}


@router.delete("/api/notifications")
async def clear_all_notifications(request: Request):
    """Delete all notifications across all keys and buckets.

    Inputs:
    - `request`: FastAPI request carrying app state.

    Outputs:
    - JSON acknowledgement confirming that all notifications were cleared.

    Why the decorator is used:
    - `@router.delete` exposes this destructive handler as an HTTP DELETE endpoint.
    """
    repo = request.app.state.runtime.repository
    repo.clear_all_notifications()
    await request.app.state.runtime.event_bus.publish("notifications.cleared_all", {})
    return {"cleared": "all"}


@router.get("/api/audit")
async def list_audit(request: Request):
    """List audit log entries newest first.

    Inputs:
    - `request`: FastAPI request carrying app state.

    Outputs:
    - JSON list of serialized audit records.

    Why the decorator is used:
    - `@router.get` exposes this read-only handler as an HTTP GET endpoint.
    """
    repo = request.app.state.runtime.repository
    return {"items": [asdict(entry) for entry in repo.list_audit_entries()]}


@router.get("/api/audit/{audit_id}")
async def get_audit(audit_id: int, request: Request):
    """Fetch one audit entry by ID.

    Inputs:
    - `audit_id`: path parameter.
    - `request`: FastAPI request carrying app state.

    Outputs:
    - JSON audit entry object or `404`.

    Why the decorator is used:
    - `@router.get` exposes this read-only handler as an HTTP GET endpoint.
    """
    repo = request.app.state.runtime.repository
    entry = repo.get_audit_entry(audit_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    return asdict(entry)


@router.post("/api/demo/random")
async def create_random_demo(request: Request):
    """Generate demo keys and send localhost demo traffic over all channels.

    Inputs:
    - `request`: FastAPI request carrying runtime settings.

    Outputs:
    - JSON payload listing generated demo keys.

    Why the decorator is used:
    - `@router.post` exposes this mutating/demo action as an HTTP endpoint.
    """
    runtime = request.app.state.runtime
    keys = await seed_random_demo(runtime.settings, 5)
    await runtime.event_bus.publish("demo.seeded", {"keys": keys})
    return {"keys": keys}


@router.post("/ingest/webhook/{api_key}")
async def ingest_webhook(api_key: str, request: Request):
    """Receive one webhook and forward it into shared ingestion logic.

    Inputs:
    - `api_key`: key string from the request path.
    - `request`: JSON request body and client metadata.

    Outputs:
    - JSON `IngestResult` with status `201` for accepted, `202` for rejected-to-audit.

    Why the decorator is used:
    - `@router.post` exposes the webhook listener as an HTTP POST endpoint.
    """
    payload = await request.json()
    result = await request.app.state.runtime.ingestion.ingest_webhook(api_key, payload, request.client.host if request.client else "")
    return JSONResponse(asdict(result), status_code=201 if result.accepted else 202)


@router.get("/api/events")
async def event_stream(request: Request):
    """Expose server-sent events for live UI refresh.

    Inputs:
    - `request`: FastAPI request carrying app state.

    Outputs:
    - Streaming SSE response with an immediate handshake event plus live updates.

    Why the decorator is used:
    - `@router.get` exposes the live event stream as an HTTP GET endpoint.
    """
    event_bus = request.app.state.runtime.event_bus

    async def stream():
        """Yield handshake and live event frames.

        Inputs:
        - None, closes over `event_bus`.

        Outputs:
        - SSE-formatted text frames for browser/TUI clients.
        """
        yield 'data: {"type":"hello","payload":{}}\n\n'
        async for message in event_bus.subscribe():
            yield f"data: {message}\n\n"
            await asyncio.sleep(0)

    return StreamingResponse(stream(), media_type="text/event-stream")
