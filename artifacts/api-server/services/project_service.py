"""ProjectService — project CRUD via storage layer. No HTTP, no LLM."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.logging import get_logger
from models.project import Project
from schemas.project import ProjectCreate, ProjectUpdate

logger = get_logger(__name__)


class ProjectNotFound(Exception):
    pass


class ProjectService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_all(self) -> list[Project]:
        return self._db.query(Project).order_by(Project.created_at.desc()).all()

    def get(self, project_id: int) -> Project:
        project = self._db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ProjectNotFound(f"Project {project_id} not found")
        return project

    def create(self, data: ProjectCreate) -> Project:
        project = Project(
            title=data.title,
            life_event=data.life_event,
            audience=data.audience,
            tone=data.tone,
            context=data.context,
            status="draft",
        )
        self._db.add(project)
        self._db.commit()
        self._db.refresh(project)
        logger.info("Created project id=%d title='%s'", project.id, project.title)
        return project

    def update(self, project_id: int, data: ProjectUpdate) -> Project:
        project = self.get(project_id)
        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(project, key, value)
        project.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(project)
        return project

    def delete(self, project_id: int) -> None:
        project = self.get(project_id)
        self._db.delete(project)
        self._db.commit()
        logger.info("Deleted project id=%d", project_id)

    def mark_status(self, project_id: int, status: str) -> None:
        project = self.get(project_id)
        project.status = status
        project.updated_at = datetime.now(timezone.utc)
        self._db.commit()
