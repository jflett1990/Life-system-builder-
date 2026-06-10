"""
Vercel / root entrypoint — exposes the Tutorial Builder FastAPI app.

Vercel's Python runtime looks for a top-level `app` in main.py. The real
application lives in artifacts/api-server/main.py; this module loads it.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import traceback

_API_SERVER_DIR = os.path.join(os.path.dirname(__file__), "artifacts", "api-server")


def _load_app():
    if _API_SERVER_DIR not in sys.path:
        sys.path.insert(0, _API_SERVER_DIR)

    spec = importlib.util.spec_from_file_location(
        "tutorial_builder_api",
        os.path.join(_API_SERVER_DIR, "main.py"),
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["tutorial_builder_api"] = module
    spec.loader.exec_module(module)
    return module.app


def _error_app(exc: BaseException):
    """Minimal ASGI app returned when the real app fails to import."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    err_app = FastAPI(title="Tutorial Builder — boot error")
    detail = str(exc)
    trace = traceback.format_exc()

    @err_app.get("/api/healthz", include_in_schema=False)
    async def healthz():
        return JSONResponse(
            status_code=503,
            content={"status": "error", "boot_error": detail},
        )

    @err_app.get("/{path:path}", include_in_schema=False)
    async def fallback(path: str = ""):
        return JSONResponse(
            status_code=503,
            content={
                "error": "Server failed to start",
                "detail": detail,
                "hint": "Check Vercel logs — usually missing Python deps or Postgres SSL.",
                "trace": trace if os.environ.get("VERCEL_ENV") == "preview" else None,
            },
        )

    return err_app


try:
    app = _load_app()
except Exception as boot_exc:
    app = _error_app(boot_exc)
