from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas.render import RenderResult
from services.render_service import RenderService, RenderError
from storage.database import get_db

router = APIRouter(prefix="/render", tags=["render"])


def _render_svc(db: Session = Depends(get_db)) -> RenderService:
    return RenderService(db)


@router.post("/{project_id}", response_model=RenderResult)
def render_project(project_id: int, svc: RenderService = Depends(_render_svc)):
    try:
        return svc.render(project_id)
    except RenderError as e:
        raise HTTPException(status_code=400, detail=str(e))
