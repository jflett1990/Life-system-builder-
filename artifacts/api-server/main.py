"""
Life System Builder — FastAPI backend entry point.

Startup sequence:
  1. Load and validate all prompt contracts from disk
  2. Start background DB initialisation (non-blocking — server comes up immediately)
  3. Mount all routers under /api
  4. Serve
"""
import os
import sys

# Ensure the api-server directory is on sys.path so all relative imports resolve
sys.path.insert(0, os.path.dirname(__file__))

import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.logging import get_logger
from core.contract_registry import validate_and_load

logger = get_logger("main")

# ── Database readiness flag ───────────────────────────────────────────
_db_ready = threading.Event()
_db_error: str | None = None

_DB_RETRY_INTERVAL = 5  # seconds between retries


def _db_init_worker() -> None:
    """Background thread: keep trying to initialise the DB until it succeeds."""
    global _db_error
    attempt = 0
    while not _db_ready.is_set():
        attempt += 1
        try:
            from storage.database import init_db
            init_db()
            _db_ready.set()
            _db_error = None
            logger.info("Database initialised successfully (attempt %d)", attempt)
            return
        except Exception as exc:
            _db_error = str(exc)
            logger.warning(
                "DB init attempt %d failed: %s — retrying in %ds…",
                attempt, exc, _DB_RETRY_INTERVAL,
            )
            time.sleep(_DB_RETRY_INTERVAL)


def get_db_ready() -> bool:
    return _db_ready.is_set()


def require_db():
    """Dependency: raises 503 if DB is not yet available."""
    from fastapi import HTTPException
    if not _db_ready.is_set():
        raise HTTPException(
            status_code=503,
            detail=f"Database initialising — please retry in a moment. ({_db_error or 'connecting…'})",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("=== Life System Builder — starting up ===")

    # 1. Load and validate all prompt contracts — fail fast on any error
    try:
        registry = validate_and_load()
        logger.info(
            "Contract registry ready: %d contracts loaded",
            len(registry.list_all()),
        )
    except Exception as e:
        logger.error("FATAL: Contract registry failed to load: %s", e)
        raise

    # 2. Ensure Playwright Chromium binary is installed.
    #    Runs `playwright install chromium` once at startup if the binary is missing.
    #    This is a no-op when the binary already exists — safe to run every time.
    #    Failure is logged as a warning only — PDF export degrades gracefully to HTML.
    try:
        import shutil
        import subprocess
        _has_system_chromium = shutil.which("chromium") or shutil.which("chromium-browser")
        if not _has_system_chromium:
            logger.info("Playwright Chromium not found on PATH — running 'playwright install chromium'…")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                logger.info("Playwright Chromium installed successfully")
            else:
                logger.warning(
                    "playwright install chromium exited with code %d — PDF export may not work. "
                    "stderr: %s",
                    result.returncode,
                    result.stderr[:500] if result.stderr else "",
                )
        else:
            logger.info("System Chromium found at %s — Playwright will use it for PDF export", _has_system_chromium)
    except Exception as _pw_err:
        logger.warning(
            "Playwright startup check failed (%s) — PDF export may be unavailable. "
            "HTML export remains fully functional.",
            _pw_err,
        )

    # 3. Start DB initialisation in background so server comes up immediately
    db_thread = threading.Thread(target=_db_init_worker, daemon=True, name="db-init")
    db_thread.start()
    logger.info("=== Startup complete (DB initialising in background) ===")

    yield

    logger.info("=== Shutting down ===")


app = FastAPI(
    title="Life System Builder API",
    description="Pipeline engine for converting life events into structured operational control systems.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────
# When ALLOWED_ORIGINS is set (production), restrict to those origins and
# allow credentials (cookies).  In development (no env var), allow all
# origins but disable credentials — the two cannot be combined per the
# browser CORS spec.
_allowed_origins = settings.get_allowed_origins()
if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ── API Key middleware ────────────────────────────────────────────────
# Set API_KEY env var to enable.  Skips auth in development (key unset).
# Read-only paths (GET /api/health, docs, openapi schema) are always open.
_OPEN_PREFIXES = ("/api/health", "/api/docs", "/api/redoc", "/api/openapi.json")
_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = settings.get_api_key()
        if not key:
            return await call_next(request)
        if request.method in _MUTATION_METHODS and not any(
            request.url.path.startswith(p) for p in _OPEN_PREFIXES
        ):
            provided = request.headers.get("X-API-Key", "")
            if provided != key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key. Provide X-API-Key header."},
                )
        return await call_next(request)


app.add_middleware(ApiKeyMiddleware)

# ── Routers ──────────────────────────────────────────────────────────
from api.routes import health, projects, pipeline, render, export, contracts, telemetry

app.include_router(health.router,     prefix="/api")
app.include_router(projects.router,   prefix="/api")
app.include_router(pipeline.router,   prefix="/api")
app.include_router(render.router,     prefix="/api")
app.include_router(export.router,     prefix="/api")
app.include_router(contracts.router,  prefix="/api")
app.include_router(telemetry.router,  prefix="/api")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
