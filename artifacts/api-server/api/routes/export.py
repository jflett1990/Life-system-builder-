from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.render import ExportBundle
from services.render_service import RenderService, RenderServiceError
from storage.database import get_db

router = APIRouter(prefix="/export", tags=["export"])


def _render_svc(db: Session = Depends(get_db)) -> RenderService:
    return RenderService(db)


@router.get("/{project_id}", response_model=ExportBundle)
def export_project(project_id: int, svc: RenderService = Depends(_render_svc)):
    try:
        return svc.export(project_id)
    except RenderServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/contracts", tags=["contracts"])
def list_contracts():
    from core.contract_registry import get_registry
    registry = get_registry()
    return {"contracts": registry.summary()}
