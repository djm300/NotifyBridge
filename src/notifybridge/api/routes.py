from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from notifybridge.core.models import Notification


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def notification_to_dict(item: Notification) -> dict:
    return {
        "id": item.id,
        "received_at": item.received_at,
        "api_key": item.api_key,
        "source_type": item.source_type,
        "assignment_type": item.assignment_type,
        "state": item.state,
        "title": item.title,
        "body": item.body,
        "raw_payload": item.raw_payload,
        "metadata": item.metadata,
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    runtime = request.app.state.runtime
    return templates.TemplateResponse(
        request,
        "index.html",
        {"settings": runtime.settings},
    )


@router.get("/api/keys")
async def list_keys(request: Request):
    repo = request.app.state.runtime.repository
    return {
        "keys": [
            {
                "api_key": item.api_key,
                "total_count": item.total_count,
                "new_count": item.new_count,
                "read_count": item.read_count,
            }
            for item in repo.list_key_summaries()
        ],
        "unassigned": {
            "enabled": repo.get_syslog_mode() == "permissive",
            "summary": asdict(repo.unassigned_summary()),
        },
    }


@router.post("/api/keys")
async def create_key(request: Request):
    payload = await request.json()
    api_key = (payload.get("api_key") or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")
    repo = request.app.state.runtime.repository
    repo.add_api_key(api_key)
    await request.app.state.runtime.event_bus.publish("keys.changed", {"api_key": api_key})
    return JSONResponse({"api_key": api_key}, status_code=201)


@router.delete("/api/keys/{api_key}")
async def delete_key(api_key: str, request: Request):
    repo = request.app.state.runtime.repository
    repo.remove_api_key(api_key)
    await request.app.state.runtime.event_bus.publish("keys.changed", {"api_key": api_key})
    return {"deleted": api_key}


@router.get("/api/notifications")
async def list_notifications(request: Request, api_key: str | None = None, assignment_type: str | None = None):
    repo = request.app.state.runtime.repository
    items = repo.list_notifications(api_key=api_key, assignment_type=assignment_type)
    return {"items": [notification_to_dict(item) for item in items]}


@router.get("/api/notifications/{notification_id}")
async def get_notification(notification_id: int, request: Request):
    repo = request.app.state.runtime.repository
    item = repo.get_notification(notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification_to_dict(item)


@router.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, request: Request):
    repo = request.app.state.runtime.repository
    if not repo.get_notification(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    repo.mark_read(notification_id)
    await request.app.state.runtime.event_bus.publish("notification.updated", {"id": notification_id})
    return {"id": notification_id, "state": "read"}


@router.delete("/api/notifications/{notification_id}")
async def delete_notification(notification_id: int, request: Request):
    repo = request.app.state.runtime.repository
    repo.delete_notification(notification_id)
    await request.app.state.runtime.event_bus.publish("notification.deleted", {"id": notification_id})
    return {"deleted": notification_id}


@router.post("/api/notifications/bulk-delete")
async def bulk_delete_notifications(request: Request):
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
    repo = request.app.state.runtime.repository
    repo.clear_notifications_for_key(api_key)
    await request.app.state.runtime.event_bus.publish("notifications.cleared", {"api_key": api_key})
    return {"cleared": api_key}


@router.get("/api/audit")
async def list_audit(request: Request):
    repo = request.app.state.runtime.repository
    return {"items": [asdict(entry) for entry in repo.list_audit_entries()]}


@router.get("/api/audit/{audit_id}")
async def get_audit(audit_id: int, request: Request):
    repo = request.app.state.runtime.repository
    entry = repo.get_audit_entry(audit_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    return asdict(entry)


@router.post("/ingest/webhook/{api_key}")
async def ingest_webhook(api_key: str, request: Request):
    payload = await request.json()
    result = await request.app.state.runtime.ingestion.ingest_webhook(api_key, payload, request.client.host if request.client else "")
    return JSONResponse(asdict(result), status_code=201 if result.accepted else 202)


@router.get("/api/events")
async def event_stream(request: Request):
    event_bus = request.app.state.runtime.event_bus

    async def stream():
        yield 'data: {"type":"hello","payload":{}}\n\n'
        async for message in event_bus.subscribe():
            yield f"data: {message}\n\n"
            await asyncio.sleep(0)

    return StreamingResponse(stream(), media_type="text/event-stream")
