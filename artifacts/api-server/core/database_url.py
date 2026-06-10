"""Resolve SQLAlchemy database URLs for local SQLite and Vercel Postgres."""
from __future__ import annotations

import os


def normalize_postgres_url(url: str) -> str:
    """Convert Vercel/Heroku-style postgres:// URLs for SQLAlchemy + psycopg2."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def resolve_database_url(*, fallback: str = "sqlite:///./tutorial_builder.db") -> str:
    """Pick the best available database URL.

    Priority (Vercel Postgres first):
      1. POSTGRES_URL          — pooled; recommended on Vercel serverless
      2. DATABASE_URL          — explicit override / other hosts
      3. POSTGRES_PRISMA_URL   — Vercel Prisma-compatible pooled URL
      4. POSTGRES_URL_NON_POOLING — direct connection (migrations / local tools)
      5. fallback              — SQLite for local dev
    """
    for key in (
        "POSTGRES_URL",
        "DATABASE_URL",
        "POSTGRES_PRISMA_URL",
        "POSTGRES_URL_NON_POOLING",
    ):
        raw = os.environ.get(key, "").strip()
        if raw:
            if raw.startswith("sqlite"):
                return raw
            return normalize_postgres_url(raw)
    return fallback
