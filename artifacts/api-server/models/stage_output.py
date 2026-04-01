import json
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from models.base import Base


class StageOutput(Base):
    __tablename__ = "stage_outputs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Parsed + schema-validated output (JSON dict)
    json_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Original raw model response string — preserved for debugging, never coerced
    raw_model_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    preview_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_progress: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
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

    # ── JSON output helpers ───────────────────────────────────────────────────

    def get_output(self) -> dict:
        if self.json_output:
            return json.loads(self.json_output)
        return {}

    def set_output(self, data: dict) -> None:
        self.json_output = json.dumps(data)

    # ── Raw model output helpers ──────────────────────────────────────────────

    def get_raw_output(self) -> str | None:
        return self.raw_model_output

    def set_raw_output(self, text: str) -> None:
        """Store the original model response string verbatim."""
        self.raw_model_output = text

    # ── Validation result helpers ─────────────────────────────────────────────

    def get_validation(self) -> dict | None:
        if self.validation_result:
            return json.loads(self.validation_result)
        return None

    def set_validation(self, data: dict) -> None:
        self.validation_result = json.dumps(data)

    # ── Sub-progress helpers ──────────────────────────────────────────────────

    def get_sub_progress(self) -> dict | None:
        if self.sub_progress:
            return json.loads(self.sub_progress)
        return None

    def set_sub_progress(self, data: dict) -> None:
        self.sub_progress = json.dumps(data)
