"""
StageOutputRepository — all SQLAlchemy access for the StageOutput model.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from models.stage_output import StageOutput


class StageOutputRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────────────

    def find_by_project_and_stage(
        self, project_id: int, stage_name: str
    ) -> StageOutput | None:
        return (
            self._db.query(StageOutput)
            .filter(
                StageOutput.project_id == project_id,
                StageOutput.stage_name == stage_name,
            )
            .first()
        )

    def find_all_for_project(self, project_id: int) -> list[StageOutput]:
        return (
            self._db.query(StageOutput)
            .filter(StageOutput.project_id == project_id)
            .order_by(StageOutput.created_at)
            .all()
        )

    def find_completed_stage_names(self, project_id: int) -> set[str]:
        rows = (
            self._db.query(StageOutput.stage_name)
            .filter(
                StageOutput.project_id == project_id,
                StageOutput.status == "complete",
            )
            .all()
        )
        return {row.stage_name for row in rows}

    # ── Mutations ─────────────────────────────────────────────────────────────

    def insert(self, stage_output: StageOutput) -> StageOutput:
        self._db.add(stage_output)
        self._db.commit()
        return stage_output

    def save(self, stage_output: StageOutput) -> StageOutput:
        self._db.commit()
        self._db.refresh(stage_output)
        return stage_output

    def delete_all_for_project(self, project_id: int) -> int:
        count = (
            self._db.query(StageOutput)
            .filter(StageOutput.project_id == project_id)
            .delete()
        )
        self._db.commit()
        return count
