"""
Pipeline routes.

Stage execution is asynchronous — routes return immediately with the current
stage row (status='running'), and a BackgroundTask drives the LLM call.
Polling (GET /projects/{id}/stages) discovers completion.
"""
import asyncio
import concurrent.futures
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from core.logging import get_logger
from core.pipeline_orchestrator import PipelineError
from schemas.stage import STAGE_NAMES, StageOutputResponse, normalize_stage_name
from schemas.validation import ValidationResultSchema
from services.pipeline_service import PipelineService
from services.project_service import ProjectNotFound, ProjectService
from services.validation_service import ValidationService
from storage.database import SessionLocal, get_db

logger = get_logger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="stage-worker")


def _pipeline_svc(db: Session = Depends(get_db)) -> PipelineService:
    return PipelineService(db)


def _validation_svc(db: Session = Depends(get_db)) -> ValidationService:
    return ValidationService(db)


def _run_stage_in_background(project_id: int, stage: str, force: bool) -> None:
    """Execute a pipeline stage in a thread-pool worker with its own DB session."""
    from datetime import datetime, timezone
    from repositories.stage_repo import StageOutputRepository

    db = SessionLocal()
    try:
        svc = PipelineService(db)
        svc.run_stage(project_id, stage, force=force)
    except Exception as e:
        logger.error("Background stage '%s' project=%d crashed: %s", stage, project_id, e)
        # Ensure the stage is marked failed — otherwise the UI stays stuck at "running/0%"
        try:
            repo = StageOutputRepository(db)
            row = repo.find_by_project_and_stage(project_id, stage)
            if row and row.status == "running":
                row.status = "failed"
                row.error_message = f"Unexpected error: {str(e)[:500]}"
                row.sub_progress = None
                row.updated_at = datetime.now(timezone.utc)
                repo.save(row)
        except Exception as inner:
            logger.error("Failed to mark stage '%s' as failed: %s", stage, inner)
    finally:
        db.close()


def _run_all_in_background(project_id: int) -> None:
    """Execute all pending pipeline stages sequentially in a background thread."""
    db = SessionLocal()
    try:
        svc = PipelineService(db)
        svc.run_full_pipeline(project_id)
    except Exception as e:
        logger.error("Background run-all project=%d crashed: %s", project_id, e)
    finally:
        db.close()


def _get_or_create_running_row(
    pipeline: PipelineService, project_id: int, stage: str, force: bool
) -> Any:
    """Return a stage row in 'running' status for use as the immediate API response.

    If the stage already exists and force=False, return it as-is (cached).
    Otherwise, upsert to 'running' immediately so the caller gets a useful row back.
    """
    from datetime import datetime, timezone
    from models.stage_output import StageOutput

    repo = pipeline._repo

    existing = repo.find_by_project_and_stage(project_id, stage)

    from repositories.stage_repo import StageOutputRepository
    completed = pipeline.completed_stages(project_id)
    if stage in completed and not force:
        return existing

    if existing:
        existing.status = "running"
        existing.error_message = None
        existing.revision_number += 1
        existing.updated_at = datetime.now(timezone.utc)
        repo.save(existing)
        return existing
    else:
        row = StageOutput(
            project_id=project_id,
            stage_name=stage,
            status="running",
            revision_number=1,
        )
        repo.insert(row)
        return row


@router.post("/{project_id}/run/{stage}", response_model=StageOutputResponse)
def run_stage(
    project_id: int,
    stage: str,
    force: bool = False,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    pipeline: PipelineService = Depends(_pipeline_svc),
):
    """
    Start a pipeline stage. Returns immediately with status='running'.
    Poll GET /projects/{project_id}/stages to discover completion.
    """
    stage = normalize_stage_name(stage)
    if stage not in STAGE_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown stage '{stage}'. Valid: {STAGE_NAMES}")

    try:
        project = pipeline._project_svc.get(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    completed = pipeline.completed_stages(project_id)

    if stage in completed and not force:
        existing = pipeline._repo.find_by_project_and_stage(project_id, stage)
        if existing:
            logger.info("Stage '%s' already complete for project %d — returning cached", stage, project_id)
            return StageOutputResponse.from_orm_with_json(existing)

    from core.pipeline_orchestrator import PipelineOrchestrator
    orch = PipelineOrchestrator()
    try:
        orch.check_upstream_complete(stage, completed)
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row = _get_or_create_running_row(pipeline, project_id, stage, force)

    _thread_pool.submit(_run_stage_in_background, project_id, stage, force)

    logger.info("Stage '%s' dispatched to background for project %d", stage, project_id)
    return StageOutputResponse.from_orm_with_json(row)


@router.post("/{project_id}/run-all", response_model=list[StageOutputResponse])
def run_full_pipeline(
    project_id: int,
    pipeline: PipelineService = Depends(_pipeline_svc),
):
    """
    Start all pending pipeline stages sequentially in the background.
    Returns immediately with the current stage rows.
    """
    try:
        project = pipeline._project_svc.get(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    _thread_pool.submit(_run_all_in_background, project_id)

    logger.info("run-all dispatched to background for project %d", project_id)

    rows = pipeline.list_stage_outputs(project_id)
    return [StageOutputResponse.from_orm_with_json(r) for r in rows]


@router.get("/{project_id}/delta-scope/{stage}")
def get_delta_scope(
    project_id: int,
    stage: str,
    pipeline: PipelineService = Depends(_pipeline_svc),
):
    """Return the set of downstream stages that would be invalidated if `stage`
    were edited. Read-only — no state changes."""
    from core.pipeline_orchestrator import PipelineOrchestrator
    stage = normalize_stage_name(stage)
    try:
        return PipelineOrchestrator().delta_scope(stage)
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _rerun_from_in_background(project_id: int, stage: str) -> None:
    """Execute invalidate_downstream + rerun_from in a thread-pool worker."""
    from datetime import datetime, timezone
    from repositories.stage_repo import StageOutputRepository

    db = SessionLocal()
    try:
        svc = PipelineService(db)
        svc.rerun_from(project_id, stage)
    except Exception as e:
        logger.error("Background rerun-from '%s' project=%d crashed: %s", stage, project_id, e)
    finally:
        db.close()


@router.post("/{project_id}/rerun-from/{stage}", response_model=list[StageOutputResponse])
def rerun_from_stage(
    project_id: int,
    stage: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    pipeline: PipelineService = Depends(_pipeline_svc),
):
    """Delta regeneration (PDR §07). Invalidate all downstream stages and
    re-execute `stage` + cascade in canonical order. Returns immediately with
    the current stage rows marked 'running'/'pending'."""
    stage = normalize_stage_name(stage)
    try:
        pipeline._project_svc.get(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    try:
        pipeline.invalidate_downstream(project_id, stage)
    except PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _thread_pool.submit(_rerun_from_in_background, project_id, stage)

    logger.info("rerun-from '%s' dispatched for project %d", stage, project_id)
    rows = pipeline.list_stage_outputs(project_id)
    return [StageOutputResponse.from_orm_with_json(r) for r in rows]


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
