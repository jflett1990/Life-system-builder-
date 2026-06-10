import os
import time
import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

_database_url = settings.get_database_url()
_is_sqlite = _database_url.startswith("sqlite")
_is_vercel = bool(os.environ.get("VERCEL"))

_engine_kwargs: dict = {
    "connect_args": {"check_same_thread": False} if _is_sqlite else {},
    "pool_pre_ping": True,
    "echo": False,
}

# Serverless-friendly pool sizing on Vercel + Postgres
if not _is_sqlite and _is_vercel:
    _engine_kwargs.update(pool_size=1, max_overflow=0, pool_recycle=300)

engine = create_engine(_database_url, **_engine_kwargs)

logger.info(
    "Database engine: dialect=%s vercel=%s",
    "sqlite" if _is_sqlite else "postgresql",
    _is_vercel,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Readiness flag — set True once init_db() succeeds.
_db_ready = threading.Event()


def mark_db_ready() -> None:
    _db_ready.set()


def is_db_ready() -> bool:
    return _db_ready.is_set()


def require_db_ready() -> None:
    """Raise HTTP 503 if the database has not yet initialised."""
    if not _db_ready.is_set():
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Database is initialising — please retry in a moment.",
        )


def get_db():
    require_db_ready()
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models.base import Base
    import models.project           # noqa: F401
    import models.stage_output      # noqa: F401
    import models.validation_result # noqa: F401
    import models.render_artifact   # noqa: F401
    import models.branding_profile  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialised")

    from storage.migrations import run_migrations
    run_migrations(engine)

    _recover_orphaned_running_stages()
    mark_db_ready()


def _recover_orphaned_running_stages() -> None:
    """Reset any stages left in 'running' state from a previous server crash or restart."""
    from sqlalchemy import text
    with SessionLocal() as db:
        result = db.execute(
            text(
                "UPDATE stage_outputs SET status = 'failed', "
                "error_message = 'Interrupted by server restart — please re-run this stage.' "
                "WHERE status = 'running'"
            )
        )
        db.commit()
        count = result.rowcount
        if count:
            logger.warning(
                "Startup recovery: reset %d orphaned 'running' stage(s) to 'failed'", count
            )
        else:
            logger.info("Startup recovery: no orphaned running stages found")
