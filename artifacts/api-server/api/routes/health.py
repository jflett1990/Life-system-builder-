from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
def health_check():
    from storage.database import is_db_ready
    db_ready = is_db_ready()
    return {
        "status": "ok" if db_ready else "degraded",
        "db": "ready" if db_ready else "initialising",
    }
