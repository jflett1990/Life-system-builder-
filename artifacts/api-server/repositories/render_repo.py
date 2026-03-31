"""
RenderArtifactRepository — all SQLAlchemy access for RenderArtifact.

One row per project — upsert semantics in the service layer.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from models.render_artifact import RenderArtifact


class RenderArtifactRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────────────

    def find_by_project(self, project_id: int) -> RenderArtifact | None:
        return (
            self._db.query(RenderArtifact)
            .filter(RenderArtifact.project_id == project_id)
            .first()
        )

    # ── Mutations ─────────────────────────────────────────────────────────────

    def insert(self, artifact: RenderArtifact) -> RenderArtifact:
        self._db.add(artifact)
        self._db.commit()
        self._db.refresh(artifact)
        return artifact

    def save(self, artifact: RenderArtifact) -> RenderArtifact:
        self._db.commit()
        self._db.refresh(artifact)
        return artifact

    def delete_for_project(self, project_id: int) -> None:
        self._db.query(RenderArtifact).filter(
            RenderArtifact.project_id == project_id
        ).delete()
        self._db.commit()
