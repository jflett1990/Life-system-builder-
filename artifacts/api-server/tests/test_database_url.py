"""Tests for database URL resolution (Vercel Postgres + SQLite)."""
from __future__ import annotations

import os
from unittest.mock import patch

from core.database_url import normalize_postgres_url, resolve_database_url


def test_normalize_postgres_url() -> None:
    assert normalize_postgres_url("postgres://u:p@host/db").startswith("postgresql+psycopg://")
    assert normalize_postgres_url("postgresql://u:p@host/db").startswith("postgresql+psycopg://")
    assert normalize_postgres_url("sqlite:///./x.db") == "sqlite:///./x.db"


def test_resolve_prefers_postgres_url() -> None:
    with patch.dict(
        os.environ,
        {
            "POSTGRES_URL": "postgres://vercel:secret@pooler/db",
            "DATABASE_URL": "sqlite:///./local.db",
        },
        clear=False,
    ):
        url = resolve_database_url()
        assert "pooler" in url
        assert url.startswith("postgresql+psycopg://")


def test_resolve_sqlite_fallback() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert resolve_database_url().startswith("sqlite:")
