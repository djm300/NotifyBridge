from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from notifybridge.api.routes import router
from notifybridge.runtime import Runtime


def create_app(runtime: Runtime) -> FastAPI:
    """Build the FastAPI application.

    Inputs:
    - `runtime`: shared application runtime and service container.

    Outputs:
    - Configured `FastAPI` app with routes and static assets mounted.
    """
    app = FastAPI(title="NotifyBridge")
    app.state.runtime = runtime
    app.mount("/static", StaticFiles(directory=str(router_static_dir())), name="static")
    app.include_router(router)
    return app


def router_static_dir():
    """Return the absolute path to bundled static assets.

    Inputs:
    - None.

    Outputs:
    - Filesystem path to the static asset directory.
    """
    return Path(__file__).resolve().parent.parent / "static"
