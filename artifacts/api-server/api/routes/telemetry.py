"""Telemetry routes — cost/spend observability for the Phase D dashboard.

Exposes a read-only view of the module-level spend registry maintained by
core.budget_controller.
"""
from fastapi import APIRouter, HTTPException

from core.budget_controller import (
    project_spend_summary,
    project_spend_events,
    clear_project_spend,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/spend/{project_id}")
def get_project_spend(project_id: int) -> dict:
    """Return aggregated spend summary for a project."""
    if project_id <= 0:
        raise HTTPException(status_code=400, detail="project_id must be positive")
    return project_spend_summary(project_id)


@router.get("/spend/{project_id}/events")
def get_project_spend_events(project_id: int, limit: int = 500) -> dict:
    """Return the raw spend event log for a project (most recent last)."""
    if project_id <= 0:
        raise HTTPException(status_code=400, detail="project_id must be positive")
    events = [e.to_dict() for e in project_spend_events(project_id)]
    if limit > 0:
        events = events[-limit:]
    return {"project_id": project_id, "count": len(events), "events": events}


@router.delete("/spend/{project_id}")
def delete_project_spend(project_id: int) -> dict:
    """Clear the spend log for a project (dev/admin use)."""
    clear_project_spend(project_id)
    return {"status": "cleared", "project_id": project_id}
