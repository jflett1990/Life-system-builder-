from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.pipeline_orchestrator import PipelineError
from schemas.stage import STAGE_NAMES, StageOutputResponse, normalize_stage_name
from schemas.validation import ValidationResultSchema
from services.pipeline_service import PipelineService
from services.project_service import ProjectNotFound, ProjectService
from services.validation_service import ValidationService
from storage.database import get_db

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _pipeline_svc(db: Session = Depends(get_db)) -> PipelineService:
    return PipelineService(db)


def _validation_svc(db: Session = Depends(get_db)) -> ValidationService:
    return ValidationService(db)


@router.post("/{project_id}/run/{stage}", response_model=StageOutputResponse)
def run_stage(
    project_id: int,
    stage: str,
    force: bool = False,
    pipeline: PipelineService = Depends(_pipeline_svc),
):
    stage = normalize_stage_name(stage)
    if stage not in STAGE_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown stage '{stage}'. Valid: {STAGE_NAMES}")
    try:
        result = pipeline.run_stage(project_id, stage, force=force)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return StageOutputResponse.from_orm_with_json(result)


@router.post("/{project_id}/run-all", response_model=list[StageOutputResponse])
def run_full_pipeline(
    project_id: int,
    pipeline: PipelineService = Depends(_pipeline_svc),
):
    try:
        results = pipeline.run_full_pipeline(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return [StageOutputResponse.from_orm_with_json(r) for r in results]


@router.post("/{project_id}/validate", response_model=ValidationResultSchema)
def validate_project(
    project_id: int,
    validation: ValidationService = Depends(_validation_svc),
):
    """
    Run the compiler-style validation engine against all completed pipeline stages.
    Returns a structured ValidationResult with verdict, per-stage breakdowns,
    and a flat defect list sorted by severity.
    No LLM call — this is pure structural and cross-stage consistency validation.
    """
    try:
        return validation.validate_project(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.get("/{project_id}/validate", response_model=ValidationResultSchema)
def get_validation_result(
    project_id: int,
    validation: ValidationService = Depends(_validation_svc),
):
    """Return the most recently persisted validation result without re-running the engine."""
    try:
        result = validation.get_persisted_result(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No validation result found for project {project_id}. Run POST /pipeline/{project_id}/validate first.",
        )
    return result
