"""
Life System Builder — FastAPI backend entry point.

Startup sequence:
  1. Initialise database (create tables)
  2. Load and validate all prompt contracts from disk
  3. Mount all routers under /api
  4. Serve
"""
import os
import sys

# Ensure the api-server directory is on sys.path so all relative imports resolve
sys.path.insert(0, os.path.dirname(__file__))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logging import get_logger
from core.contract_registry import validate_and_load
from storage.database import init_db
from api.routes import health, projects, pipeline, render, export

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("=== Life System Builder — starting up ===")

    # 1. Initialise database
    init_db()

    # 2. Load and validate all prompt contracts — fail fast on any error
    try:
        registry = validate_and_load()
        logger.info(
            "Contract registry ready: %d contracts loaded",
            len(registry.list_all()),
        )
    except Exception as e:
        logger.error("FATAL: Contract registry failed to load: %s", e)
        raise

    logger.info("=== Startup complete ===")
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

# CORS — allow the Vite frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────
app.include_router(health.router,    prefix="/api")
app.include_router(projects.router,  prefix="/api")
app.include_router(pipeline.router,  prefix="/api")
app.include_router(render.router,    prefix="/api")
app.include_router(export.router,    prefix="/api")


# ── Contracts admin endpoint ─────────────────────────────────────────
@app.get("/api/contracts", tags=["contracts"])
def list_contracts():
    """List all registered prompt contracts (name, version, stage, output_mode)."""
    from core.contract_registry import get_registry
    return {"contracts": get_registry().summary()}


@app.get("/api/contracts/{name}", tags=["contracts"])
def get_contract(name: str, version: str | None = None):
    """Get full contract definition by name (and optional version)."""
    from core.contract_registry import get_registry, ContractRegistryError
    from fastapi import HTTPException
    try:
        contract = get_registry().resolve(name, version)
        return contract.raw
    except ContractRegistryError as e:
        raise HTTPException(status_code=404, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
