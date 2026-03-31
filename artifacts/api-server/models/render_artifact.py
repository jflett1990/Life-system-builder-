"""
RenderArtifact — persists the last rendered HTML bundle for a project.

One row per project; a new render replaces the previous row via upsert.
`html_bundle_path` points to a file on disk for large exports, but for
the current MVP the full HTML is also stored in-line (via the export route)
so this row is mainly a cache key and metadata record.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class RenderArtifact(Base):
    __tablename__ = "render_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    manifest_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_bundle_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def get_manifest(self) -> dict[str, Any] | None:
        if self.manifest_json:
            return json.loads(self.manifest_json)
        return None

    def set_manifest(self, data: dict[str, Any]) -> None:
        self.manifest_json = json.dumps(data, ensure_ascii=False)
