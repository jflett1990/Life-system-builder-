from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
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


def _recover_orphaned_running_stages() -> None:
    """Reset any stages left in 'running' state from a previous server crash or restart.

    Stages in 'running' state with no active request are permanently stuck — the background
    thread was killed when the server died. Mark them 'failed' so users can re-run them.
    """
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
