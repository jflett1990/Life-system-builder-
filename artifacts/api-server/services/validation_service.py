"""
ValidationService — runs the compiler-style validation engine and persists results.

Delegates all DB access to ValidationRepository.

Flow:
  1. Fetch all completed stage outputs via PipelineService
  2. Run ValidationEngine.run() — all per-stage and cross-stage rules
  3. Persist one project-level summary row (stage_name=None) via repository
  4. Persist per-stage result rows (stage_name set) for granular reporting
  5. Return ValidationResultSchema to the API layer

No LLM calls. Pure structural and logical validation.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core.logging import get_logger
from models.validation_result import ValidationResultModel
from repositories.validation_repo import ValidationRepository
from schemas.validation import ValidationResultSchema
from services.pipeline_service import PipelineService
from services.project_service import ProjectNotFound, ProjectService
from validators.engine import ValidationEngine

logger = get_logger(__name__)

_engine = ValidationEngine()


class ValidationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = ValidationRepository(db)
        self._pipeline = PipelineService(db)

    def validate_project(self, project_id: int) -> ValidationResultSchema:
        try:
            ProjectService(self._db).get(project_id)
        except ProjectNotFound:
            raise

        stage_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        result = _engine.run(project_id=project_id, stage_outputs=stage_outputs)

        self._persist_summary(project_id, result)
        self._persist_stage_results(project_id, result)

        return ValidationResultSchema.from_engine_result(result)

    def get_persisted_result(self, project_id: int) -> ValidationResultSchema | None:
        row = self._repo.find_project_summary(project_id)
        if not row:
            return None
        data = row.get_result()
        if not data:
            return None
        return ValidationResultSchema(**data)

    # ── Persistence ─────────────────────────────────────────────────────────────

    def _persist_summary(self, project_id: int, result: Any) -> None:
        result_dict = result.to_dict()
        row = self._repo.find_project_summary(project_id)

        if row:
            row.verdict = result.verdict.value
            row.result = result.verdict.value
            row.blocked_handoff = result.blocked_handoff
            row.total_defects = len(result.all_defects)
            row.fatal_count = result.fatal_count
            row.error_count = result.error_count
            row.warning_count = result.warning_count
            row.summary = _build_summary_text(result)
            row.set_defects([_defect_to_dict(d) for d in result.all_defects])
            row.validated_at = result.validated_at
            row.set_result(result_dict)
            self._repo.save(row)
        else:
            row = ValidationResultModel(
                project_id=project_id,
                stage_name=None,
                verdict=result.verdict.value,
                result=result.verdict.value,
                blocked_handoff=result.blocked_handoff,
                total_defects=len(result.all_defects),
                fatal_count=result.fatal_count,
                error_count=result.error_count,
                warning_count=result.warning_count,
                summary=_build_summary_text(result),
                validated_at=result.validated_at,
            )
            row.set_defects([_defect_to_dict(d) for d in result.all_defects])
            row.set_result(result_dict)
            self._repo.insert(row)

        logger.info(
            "Persisted validation summary: project=%d verdict=%s defects=%d",
            project_id, result.verdict.value, len(result.all_defects),
        )

    def _persist_stage_results(self, project_id: int, result: Any) -> None:
        """Upsert one row per stage containing its individual defects."""
        per_stage: dict[str, list] = {}
        for defect in result.all_defects:
            sn = _stage_name_of(defect)
            if sn:
                per_stage.setdefault(sn, []).append(defect)

        for stage_name, defects in per_stage.items():
            fatal = sum(1 for d in defects if _severity(d) == "fatal")
            errors = sum(1 for d in defects if _severity(d) == "error")
            stage_verdict = "fail" if (fatal or errors) else ("warning" if defects else "pass")

            defect_dicts = [_defect_to_dict(d) for d in defects]
            row = self._repo.find_stage_result(project_id, stage_name)

            if row:
                row.verdict = stage_verdict
                row.result = stage_verdict
                row.blocked_handoff = bool(fatal)
                row.total_defects = len(defects)
                row.fatal_count = fatal
                row.error_count = errors
                row.warning_count = len(defects) - fatal - errors
                row.summary = f"{len(defects)} defect(s): {fatal} fatal, {errors} error"
                row.validated_at = result.validated_at
                row.set_defects(defect_dicts)
                self._repo.save(row)
            else:
                row = ValidationResultModel(
                    project_id=project_id,
                    stage_name=stage_name,
                    verdict=stage_verdict,
                    result=stage_verdict,
                    blocked_handoff=bool(fatal),
                    total_defects=len(defects),
                    fatal_count=fatal,
                    error_count=errors,
                    warning_count=len(defects) - fatal - errors,
                    summary=f"{len(defects)} defect(s): {fatal} fatal, {errors} error",
                    validated_at=result.validated_at,
                )
                row.set_defects(defect_dicts)
                self._repo.insert(row)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_summary_text(result: Any) -> str:
    d = len(result.all_defects)
    return (
        f"Verdict: {result.verdict.value}. "
        f"{d} defect(s) — {result.fatal_count} fatal, "
        f"{result.error_count} error, {result.warning_count} warning."
    )


def _defect_to_dict(defect: Any) -> dict:
    if isinstance(defect, dict):
        return defect
    if hasattr(defect, "__dict__"):
        return {k: (v.value if hasattr(v, "value") else v) for k, v in defect.__dict__.items()}
    return {}


def _stage_name_of(defect: Any) -> str | None:
    if hasattr(defect, "stage_name"):
        return defect.stage_name
    if isinstance(defect, dict):
        return defect.get("stage_name")
    return None


def _severity(defect: Any) -> str:
    if hasattr(defect, "severity"):
        s = defect.severity
        return s.value if hasattr(s, "value") else str(s)
    if isinstance(defect, dict):
        return defect.get("severity", "")
    return ""
