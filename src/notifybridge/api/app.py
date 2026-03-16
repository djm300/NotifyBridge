from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from notifybridge.api.routes import router
from notifybridge.runtime import Runtime


def create_app(runtime: Runtime) -> FastAPI:
    app = FastAPI(title="NotifyBridge")
    app.state.runtime = runtime
    app.mount("/static", StaticFiles(directory=str(router_static_dir())), name="static")
    app.include_router(router)
    return app


def router_static_dir():
    return Path(__file__).resolve().parent.parent / "static"
