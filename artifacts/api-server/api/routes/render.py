from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from schemas.render import RenderResult
from services.render_service import RenderService, RenderServiceError
from storage.database import get_db

router = APIRouter(prefix="/render", tags=["render"])


def _render_svc(db: Session = Depends(get_db)) -> RenderService:
    return RenderService(db)


@router.post("/{project_id}", response_model=RenderResult)
def render_project(project_id: int, svc: RenderService = Depends(_render_svc)):
    try:
        return svc.render(project_id)
    except RenderServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/manifest")
def get_manifest(project_id: int, svc: RenderService = Depends(_render_svc)):
    """Return the render manifest — ordered page list with archetypes."""
    try:
        return svc.get_manifest(project_id)
    except RenderServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/preview", response_class=HTMLResponse)
def preview_project(project_id: int, svc: RenderService = Depends(_render_svc)):
    """Return the full rendered HTML for browser preview."""
    try:
        result = svc.render(project_id)
        return HTMLResponse(content=result.html, status_code=200)
    except RenderServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/page/{page_id}", response_class=HTMLResponse)
def preview_page(project_id: int, page_id: str, svc: RenderService = Depends(_render_svc)):
    """Return the HTML for a single page — for frontend iframe previews."""
    try:
        html = svc.render_page_preview(project_id, page_id)
        return HTMLResponse(content=html, status_code=200)
    except RenderServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
