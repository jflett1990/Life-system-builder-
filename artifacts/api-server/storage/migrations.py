"""
Structured migration runner for Life System Builder.

Runs migrations in order at startup, skipping any that have already been applied.
Supports both SQLite (local dev) and PostgreSQL (production/Replit).

Migrations are functions rather than raw SQL strings so they can branch
on the detected dialect.
"""
from __future__ import annotations

import logging
from typing import Callable
from sqlalchemy import text, inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dialect(engine: Engine) -> str:
    return engine.dialect.name  # "sqlite" or "postgresql"


def _column_exists(conn, table: str, column: str, dialect: str) -> bool:
    if dialect == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
        return any(row[1] == column for row in rows)
    else:
        row = conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ), {"t": table, "c": column}).fetchone()
        return row is not None


def _table_exists(conn, table: str, dialect: str) -> bool:
    if dialect == "sqlite":
        row = conn.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t"
        ), {"t": table}).fetchone()
        return row is not None
    else:
        row = conn.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t"
        ), {"t": table}).fetchone()
        return row is not None


def _unique_constraint_exists(conn, table: str, column: str, dialect: str) -> bool:
    if dialect == "sqlite":
        rows = conn.execute(text(f"PRAGMA index_list('{table}')")).fetchall()
        for row in rows:
            if row[2]:  # unique=1
                idx_rows = conn.execute(text(f"PRAGMA index_info('{row[1]}')")).fetchall()
                if any(r[2] == column for r in idx_rows):
                    return True
        return False
    else:
        row = conn.execute(text(
            "SELECT 1 FROM information_schema.table_constraints tc "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.constraint_type = 'UNIQUE' "
            "  AND tc.table_name = :t AND ccu.column_name = :c"
        ), {"t": table, "c": column}).fetchone()
        return row is not None


def _add_column_if_missing(conn, table: str, column: str, col_type: str, dialect: str) -> None:
    if not _column_exists(conn, table, column, dialect):
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
        logger.debug("Added column %s.%s", table, column)


# ---------------------------------------------------------------------------
# Individual migrations
# ---------------------------------------------------------------------------

def _m001_add_project_columns(conn, dialect: str) -> None:
    """Add formatting_profile and artifact_density to projects."""
    _add_column_if_missing(conn, "projects", "formatting_profile", "VARCHAR(100)", dialect)
    _add_column_if_missing(conn, "projects", "artifact_density", "VARCHAR(50)", dialect)


def _m002_add_stage_preview_text(conn, dialect: str) -> None:
    """Add preview_text to stage_outputs."""
    _add_column_if_missing(conn, "stage_outputs", "preview_text", "TEXT", dialect)


def _m003_rebuild_validation_results(conn, dialect: str) -> None:
    """
    Extend validation_results:
      - Remove UNIQUE constraint on project_id (allows per-stage rows)
      - Add stage_name, result, summary, defects_json columns

    SQLite: table recreation (no ALTER CONSTRAINT support)
    PostgreSQL: DROP CONSTRAINT + ADD COLUMN
    """
    ts = "DATETIME" if dialect == "sqlite" else "TIMESTAMPTZ"
    bool_false = "0" if dialect == "sqlite" else "FALSE"

    # Add new columns first (safe if constraint removal is handled separately)
    _add_column_if_missing(conn, "validation_results", "stage_name", "VARCHAR(100)", dialect)
    _add_column_if_missing(conn, "validation_results", "result", "VARCHAR(30)", dialect)
    _add_column_if_missing(conn, "validation_results", "summary", "TEXT", dialect)
    _add_column_if_missing(conn, "validation_results", "defects_json", "TEXT", dialect)

    # Copy verdict → result for existing rows
    conn.execute(text(
        "UPDATE validation_results SET result = verdict WHERE result IS NULL"
    ))

    # Remove unique constraint on project_id
    if _unique_constraint_exists(conn, "validation_results", "project_id", dialect):
        if dialect == "sqlite":
            # SQLite: recreate table without the unique constraint
            conn.execute(text(f"""
                CREATE TABLE validation_results_v2 (
                    id              INTEGER PRIMARY KEY,
                    project_id      INTEGER NOT NULL
                                        REFERENCES projects(id) ON DELETE CASCADE,
                    stage_name      VARCHAR(100),
                    verdict         VARCHAR(30) NOT NULL,
                    result          VARCHAR(30),
                    blocked_handoff BOOLEAN NOT NULL DEFAULT {bool_false},
                    total_defects   INTEGER NOT NULL DEFAULT 0,
                    fatal_count     INTEGER NOT NULL DEFAULT 0,
                    error_count     INTEGER NOT NULL DEFAULT 0,
                    warning_count   INTEGER NOT NULL DEFAULT 0,
                    summary         TEXT,
                    defects_json    TEXT,
                    result_json     TEXT,
                    validated_at    {ts} NOT NULL
                )
            """))
            conn.execute(text("""
                INSERT INTO validation_results_v2
                SELECT id, project_id, stage_name, verdict, result,
                       blocked_handoff, total_defects, fatal_count, error_count,
                       warning_count, summary, defects_json, result_json, validated_at
                FROM validation_results
            """))
            conn.execute(text("DROP TABLE validation_results"))
            conn.execute(text("ALTER TABLE validation_results_v2 RENAME TO validation_results"))
            conn.execute(text("CREATE INDEX ix_validation_results_id ON validation_results(id)"))
            conn.execute(text("CREATE INDEX ix_validation_results_project_id ON validation_results(project_id)"))
        else:
            # PostgreSQL: find and drop the unique constraint by name
            row = conn.execute(text(
                "SELECT tc.constraint_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.constraint_column_usage ccu "
                "  ON tc.constraint_name = ccu.constraint_name "
                "WHERE tc.constraint_type = 'UNIQUE' "
                "  AND tc.table_name = 'validation_results' "
                "  AND ccu.column_name = 'project_id'"
            )).fetchone()
            if row:
                conn.execute(text(f"ALTER TABLE validation_results DROP CONSTRAINT {row[0]}"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_validation_results_project_id "
                "ON validation_results(project_id)"
            ))


def _m004_create_render_artifacts(conn, dialect: str) -> None:
    """Create render_artifacts table."""
    if _table_exists(conn, "render_artifacts", dialect):
        return
    ts = "DATETIME" if dialect == "sqlite" else "TIMESTAMPTZ"
    conn.execute(text(f"""
        CREATE TABLE render_artifacts (
            id              {'INTEGER' if dialect == 'sqlite' else 'SERIAL'} PRIMARY KEY,
            project_id      INTEGER NOT NULL UNIQUE
                                REFERENCES projects(id) ON DELETE CASCADE,
            manifest_json   TEXT,
            html_bundle_path TEXT,
            page_count      INTEGER,
            created_at      {ts} NOT NULL,
            updated_at      {ts} NOT NULL
        )
    """))
    conn.execute(text("CREATE INDEX ix_render_artifacts_project_id ON render_artifacts(project_id)"))


def _m006_add_raw_model_output(conn, dialect: str) -> None:
    """
    Add raw_model_output column to stage_outputs.

    This column stores the original model response string exactly as returned,
    separate from json_output which holds the parsed + validated data.
    Allows debugging malformed outputs without losing the raw content.
    """
    _add_column_if_missing(conn, "stage_outputs", "raw_model_output", "TEXT", dialect)


def _m007_add_sub_progress_to_stage_outputs(conn, dialect: str) -> None:
    """
    Add sub_progress column to stage_outputs.

    Stores live chapter-level progress during chapter_expansion as a JSON string:
    { "completed": N, "total": N, "last_domain": "Chapter name" }
    Allows the frontend to show per-chapter progress without WebSockets.
    """
    _add_column_if_missing(conn, "stage_outputs", "sub_progress", "TEXT", dialect)


def _m005_create_branding_profiles(conn, dialect: str) -> None:
    """Create branding_profiles table."""
    if _table_exists(conn, "branding_profiles", dialect):
        return
    ts = "DATETIME" if dialect == "sqlite" else "TIMESTAMPTZ"
    bool_false = "0" if dialect == "sqlite" else "FALSE"
    conn.execute(text(f"""
        CREATE TABLE branding_profiles (
            id                  {'INTEGER' if dialect == 'sqlite' else 'SERIAL'} PRIMARY KEY,
            name                VARCHAR(255) NOT NULL UNIQUE,
            description         TEXT,
            primary_color       VARCHAR(20),
            accent_color        VARCHAR(20),
            text_color          VARCHAR(20),
            heading_font        VARCHAR(100),
            body_font           VARCHAR(100),
            logo_url            TEXT,
            token_overrides_json TEXT,
            is_default          BOOLEAN NOT NULL DEFAULT {bool_false},
            created_at          {ts} NOT NULL,
            updated_at          {ts} NOT NULL
        )
    """))
    conn.execute(text("CREATE INDEX ix_branding_profiles_id ON branding_profiles(id)"))


# ---------------------------------------------------------------------------
# Migration registry — (version, name, fn) — append only
# ---------------------------------------------------------------------------

MigrationFn = Callable[[object, str], None]

MIGRATIONS: list[tuple[int, str, MigrationFn]] = [
    (1, "add_formatting_profile_and_artifact_density_to_projects", _m001_add_project_columns),
    (2, "add_preview_text_to_stage_outputs", _m002_add_stage_preview_text),
    (3, "rebuild_validation_results_drop_unique_add_columns", _m003_rebuild_validation_results),
    (4, "create_render_artifacts", _m004_create_render_artifacts),
    (5, "create_branding_profiles", _m005_create_branding_profiles),
    (6, "add_raw_model_output_to_stage_outputs", _m006_add_raw_model_output),
    (7, "add_sub_progress_to_stage_outputs", _m007_add_sub_progress_to_stage_outputs),
]


# ---------------------------------------------------------------------------
# Schema migrations table
# ---------------------------------------------------------------------------

def _ensure_migrations_table(conn, dialect: str) -> None:
    ts = "DATETIME" if dialect == "sqlite" else "TIMESTAMPTZ"
    default_ts = "datetime('now')" if dialect == "sqlite" else "CURRENT_TIMESTAMP"
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            applied_at  {ts} NOT NULL DEFAULT ({default_ts})
        )
    """))
    conn.commit()


def _applied_versions(conn) -> set[int]:
    rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
    return {row[0] for row in rows}


def _record_migration(conn, version: int, name: str) -> None:
    conn.execute(
        text("INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"),
        {"v": version, "n": name},
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_migrations(engine: Engine) -> None:
    """
    Apply all pending migrations in version order.
    Called once at application startup, after create_all.
    """
    dialect = _dialect(engine)
    logger.debug("Migration runner using dialect: %s", dialect)

    with engine.connect() as conn:
        _ensure_migrations_table(conn, dialect)
        applied = _applied_versions(conn)

        pending = [m for m in MIGRATIONS if m[0] not in applied]
        if not pending:
            latest = max((m[0] for m in MIGRATIONS), default=0)
            logger.debug("All migrations up to date (latest: %d)", latest)
            return

        for version, name, fn in sorted(pending, key=lambda m: m[0]):
            logger.info("Applying migration %03d: %s", version, name)
            try:
                fn(conn, dialect)
                conn.commit()
                _record_migration(conn, version, name)
                logger.info("Migration %03d complete: %s", version, name)
            except Exception as exc:
                conn.rollback()
                logger.error("Migration %03d failed: %s", version, exc)
                raise RuntimeError(
                    f"Database migration {version} ({name}) failed: {exc}"
                ) from exc

    logger.info("Migrations complete — %d applied", len(pending))
