"""
ValidationRepository — all SQLAlchemy access for ValidationResultModel.

Rows with stage_name IS NULL represent the project-level aggregate summary.
Rows with stage_name set represent per-stage pass/fail records.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from models.validation_result import ValidationResultModel


class ValidationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Project-level summary (stage_name IS NULL) ────────────────────────────

    def find_project_summary(self, project_id: int) -> ValidationResultModel | None:
        return (
            self._db.query(ValidationResultModel)
            .filter(
                ValidationResultModel.project_id == project_id,
                ValidationResultModel.stage_name.is_(None),
            )
            .first()
        )

    # ── Per-stage results (stage_name IS NOT NULL) ────────────────────────────

    def find_stage_result(
        self, project_id: int, stage_name: str
    ) -> ValidationResultModel | None:
        return (
            self._db.query(ValidationResultModel)
            .filter(
                ValidationResultModel.project_id == project_id,
                ValidationResultModel.stage_name == stage_name,
            )
            .first()
        )

    def find_all_stage_results(
        self, project_id: int
    ) -> list[ValidationResultModel]:
        return (
            self._db.query(ValidationResultModel)
            .filter(
                ValidationResultModel.project_id == project_id,
                ValidationResultModel.stage_name.isnot(None),
            )
            .order_by(ValidationResultModel.stage_name)
            .all()
        )

    # ── Mutations ─────────────────────────────────────────────────────────────

    def insert(self, row: ValidationResultModel) -> ValidationResultModel:
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def save(self, row: ValidationResultModel) -> ValidationResultModel:
        self._db.commit()
        self._db.refresh(row)
        return row

    def delete_all_for_project(self, project_id: int) -> int:
        count = (
            self._db.query(ValidationResultModel)
            .filter(ValidationResultModel.project_id == project_id)
            .delete()
        )
        self._db.commit()
        return count
