"""
ValidationResultModel — persists per-stage and project-level validation results.

Rows where stage_name IS NULL represent a project-level summary produced after
running the full validation engine.  Rows where stage_name IS NOT NULL represent
the per-stage pass/fail verdict extracted from that summary.

The migration removes the UNIQUE constraint from project_id so both row types
can coexist for the same project.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ValidationResultModel(Base):
    __tablename__ = "validation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    result: Mapped[str | None] = mapped_column(String(30), nullable=True)

    blocked_handoff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    total_defects: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fatal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    defects_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def set_result(self, data: dict[str, Any]) -> None:
        self.result_json = json.dumps(data, ensure_ascii=False)

    def get_result(self) -> dict[str, Any] | None:
        if self.result_json:
            return json.loads(self.result_json)
        return None

    def get_defects(self) -> list[dict[str, Any]]:
        if self.defects_json:
            return json.loads(self.defects_json)
        return []

    def set_defects(self, defects: list[dict[str, Any]]) -> None:
        self.defects_json = json.dumps(defects, ensure_ascii=False)
