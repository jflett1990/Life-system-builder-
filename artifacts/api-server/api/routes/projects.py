from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from schemas.pipeline import ProjectSummary, PipelineStageSummary
from schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from schemas.stage import STAGE_NAMES, StageOutputResponse, normalize_stage_name
from services.pipeline_service import PipelineService
from services.project_service import ProjectNotFound, ProjectService
from storage.database import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_svc(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def _pipeline_svc(db: Session = Depends(get_db)) -> PipelineService:
    return PipelineService(db)


@router.get("", response_model=list[ProjectResponse])
def list_projects(svc: ProjectService = Depends(_project_svc)):
    return svc.list_all()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, svc: ProjectService = Depends(_project_svc)):
    return svc.create(body)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, svc: ProjectService = Depends(_project_svc)):
    try:
        return svc.get(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, body: ProjectUpdate, svc: ProjectService = Depends(_project_svc)):
    try:
        return svc.update(project_id, body)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, svc: ProjectService = Depends(_project_svc)):
    try:
        svc.delete(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.post("/{project_id}/duplicate", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def duplicate_project(project_id: int, svc: ProjectService = Depends(_project_svc)):
    """Create a copy of a project with a fresh pipeline (no stage outputs)."""
    try:
        return svc.duplicate(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


@router.get("/{project_id}/stages", response_model=list[StageOutputResponse])
def list_stages(project_id: int, pipeline: PipelineService = Depends(_pipeline_svc)):
    rows = pipeline.list_stage_outputs(project_id)
    return [StageOutputResponse.from_orm_with_json(r) for r in rows]


@router.get("/{project_id}/stages/{stage}", response_model=StageOutputResponse)
def get_stage(project_id: int, stage: str, pipeline: PipelineService = Depends(_pipeline_svc)):
    stage = normalize_stage_name(stage)
    if stage not in STAGE_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown stage '{stage}'")
    row = pipeline.get_stage_output(project_id, stage)
    if not row:
        raise HTTPException(status_code=404, detail=f"Stage '{stage}' not found for project {project_id}")
    return StageOutputResponse.from_orm_with_json(row)


@router.get("/{project_id}/summary", response_model=ProjectSummary)
def project_summary(
    project_id: int,
    svc: ProjectService = Depends(_project_svc),
    pipeline: PipelineService = Depends(_pipeline_svc),
):
    try:
        project = svc.get(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    stage_rows = pipeline.list_stage_outputs(project_id)
    stage_map = {r.stage_name: r for r in stage_rows}
    completed = sum(1 for r in stage_rows if r.status == "complete")

    stage_summaries = [
        PipelineStageSummary(
            stage=s,
            status=stage_map[s].status if s in stage_map else "pending",
            revision=stage_map[s].revision_number if s in stage_map else 0,
        )
        for s in STAGE_NAMES
    ]

    return ProjectSummary(
        project_id=project_id,
        title=project.title,
        life_event=project.life_event,
        total_stages=len(STAGE_NAMES),
        completed_stages=completed,
        stages=stage_summaries,
    )
