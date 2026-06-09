"""Serve the built React frontend from FastAPI (used on Vercel and single-process deploys)."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.logging import get_logger

logger = get_logger(__name__)

_API_SERVER_DIR = Path(__file__).resolve().parent
_DEFAULT_DIST = _API_SERVER_DIR.parent / "life-system-builder" / "dist" / "public"


def resolve_frontend_dist() -> Path | None:
    override = os.environ.get("FRONTEND_DIST", "").strip()
    dist = Path(override) if override else _DEFAULT_DIST
    if dist.is_dir() and (dist / "index.html").is_file():
        return dist
    return None


def mount_frontend(app: FastAPI) -> bool:
    """Mount SPA static assets. Returns True if the frontend bundle was found."""
    dist = resolve_frontend_dist()
    if dist is None:
        logger.warning("Frontend dist not found — only /api routes will be served")
        return False

    logger.info("Serving frontend from %s", dist)
    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        return FileResponse(dist / "favicon.svg")

    @app.get("/opengraph.jpg", include_in_schema=False)
    async def opengraph():
        return FileResponse(dist / "opengraph.jpg")

    @app.get("/", include_in_schema=False)
    async def spa_index():
        return FileResponse(dist / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api") or full_path.startswith("assets"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")

    return True
