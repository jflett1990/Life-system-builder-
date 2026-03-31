"""
ValidationService — drives the compiler-style validation engine and persists results.

Flow:
  1. Fetch all completed stage outputs for the project
  2. Run ValidationEngine.run() — all per-stage and cross-stage rules
  3. Persist the ValidationResult to the database (upsert on project_id)
  4. Return ValidationResultSchema for the API

No LLM calls — this is pure structural and logical validation.
The life_system_validation_agent contract is reserved for future LLM-assisted
semantic auditing as an optional second pass.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core.logging import get_logger
from models.validation_result import ValidationResultModel
from schemas.validation import ValidationResultSchema
from services.pipeline_service import PipelineService
from services.project_service import ProjectNotFound
from validators.engine import ValidationEngine

logger = get_logger(__name__)

_engine = ValidationEngine()


class ValidationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._pipeline = PipelineService(db)

    def validate_project(self, project_id: int) -> ValidationResultSchema:
        """
        Run the full compiler-style validation engine against all completed
        stage outputs for a project. Persists the result and returns the schema.
        """
        # Verify project exists
        from services.project_service import ProjectService
        try:
            ProjectService(self._db).get(project_id)
        except ProjectNotFound:
            raise

        stage_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)

        result = _engine.run(project_id=project_id, stage_outputs=stage_outputs)

        self._persist(project_id, result)

        return ValidationResultSchema.from_engine_result(result)

    def get_persisted_result(self, project_id: int) -> ValidationResultSchema | None:
        """Return the most recent persisted validation result for a project, if any."""
        row = self._fetch_row(project_id)
        if not row:
            return None
        data = row.get_result()
        if not data:
            return None
        return ValidationResultSchema(**data)

    def _persist(self, project_id: int, result: Any) -> None:
        result_dict = result.to_dict()
        row = self._fetch_row(project_id)
        if row:
            # Update existing row
            row.verdict = result.verdict.value
            row.blocked_handoff = result.blocked_handoff
            row.total_defects = len(result.all_defects)
            row.fatal_count = result.fatal_count
            row.error_count = result.error_count
            row.warning_count = result.warning_count
            row.validated_at = result.validated_at
            row.set_result(result_dict)
        else:
            row = ValidationResultModel(
                project_id=project_id,
                verdict=result.verdict.value,
                blocked_handoff=result.blocked_handoff,
                total_defects=len(result.all_defects),
                fatal_count=result.fatal_count,
                error_count=result.error_count,
                warning_count=result.warning_count,
                validated_at=result.validated_at,
            )
            row.set_result(result_dict)
            self._db.add(row)

        self._db.commit()
        logger.info(
            "Persisted validation result: project=%d verdict=%s defects=%d",
            project_id, result.verdict.value, len(result.all_defects),
        )

    def _fetch_row(self, project_id: int) -> ValidationResultModel | None:
        return (
            self._db.query(ValidationResultModel)
            .filter(ValidationResultModel.project_id == project_id)
            .first()
        )
