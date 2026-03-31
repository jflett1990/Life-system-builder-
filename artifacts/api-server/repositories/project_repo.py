"""
ProjectRepository — all SQLAlchemy access for the Project model.

Owns:  queries, inserts, updates, deletes.
Does not own: business logic, LLM calls, HTTP concerns.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from models.project import Project


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────────────

    def find_all(self) -> list[Project]:
        return (
            self._db.query(Project)
            .order_by(Project.created_at.desc())
            .all()
        )

    def find_by_id(self, project_id: int) -> Project | None:
        return self._db.query(Project).filter(Project.id == project_id).first()

    # ── Mutations ─────────────────────────────────────────────────────────────

    def insert(self, project: Project) -> Project:
        self._db.add(project)
        self._db.commit()
        self._db.refresh(project)
        return project

    def save(self, project: Project) -> Project:
        self._db.commit()
        self._db.refresh(project)
        return project

    def delete(self, project: Project) -> None:
        self._db.delete(project)
        self._db.commit()
