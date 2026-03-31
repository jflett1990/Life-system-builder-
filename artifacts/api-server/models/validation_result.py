"""
ValidationResult SQLAlchemy model — persists full validation results per project.

One row per validation run; a new run replaces the previous one for the same project.
The full result JSON is stored in `result_json` so the frontend can restore it
without re-running the engine.
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

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
    project_id:  Mapped[int]  = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True, unique=True,  # one result per project
    )
    verdict:          Mapped[str]  = mapped_column(String(30), nullable=False)
    blocked_handoff:  Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_defects:    Mapped[int]  = mapped_column(Integer, nullable=False, default=0)
    fatal_count:      Mapped[int]  = mapped_column(Integer, nullable=False, default=0)
    error_count:      Mapped[int]  = mapped_column(Integer, nullable=False, default=0)
    warning_count:    Mapped[int]  = mapped_column(Integer, nullable=False, default=0)
    result_json:      Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at:     Mapped[datetime] = mapped_column(
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
