"""
ArtifactRegistry — content-addressed artifact store for the v2 pipeline.

Key design (PDR §05):
  - Keyed by (project_id, stage, model_id, contract_version)
  - Artifacts are immutable on write; reruns produce new revisions
  - Near-duplicate detection for iterative user edits
  - Lightweight in-memory + optional JSON-file persistence (no new DB table required
    for Phase A — the existing stage_outputs table remains the source of truth)

Phase A usage: wires new pipeline artifacts (project_brief, research_graph, etc.)
without breaking existing stage_outputs flow.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArtifactRevision:
    """An immutable snapshot of a pipeline artifact."""
    revision_id: str           # content-addressed SHA-256 prefix
    project_id: int
    stage: str
    model_id: str
    contract_version: str
    schema_version: str
    payload: dict[str, Any]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "project_id": self.project_id,
            "stage": self.stage,
            "model_id": self.model_id,
            "contract_version": self.contract_version,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
        }


def _content_hash(payload: dict[str, Any]) -> str:
    """Return a short SHA-256 hex digest of the JSON-serialised payload."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class ArtifactRegistry:
    """Content-addressed store for pipeline stage artifacts.

    Stores all revisions in memory; callers can persist/restore via
    ``snapshot()`` / ``restore()``.

    Cache key: (project_id, stage, model_id, contract_version)
    Separate revisions are kept when any component of the key changes,
    enabling safe delta reruns and meaningful diffing.
    """

    def __init__(self) -> None:
        # _store maps cache_key → list[ArtifactRevision] (most recent last)
        self._store: dict[str, list[ArtifactRevision]] = {}

    # ── Write ──────────────────────────────────────────────────────────────────

    def write(
        self,
        *,
        project_id: int,
        stage: str,
        model_id: str,
        contract_version: str,
        schema_version: str,
        payload: dict[str, Any],
    ) -> ArtifactRevision:
        """Write a new immutable artifact revision.

        Never mutates an existing revision. Always appends.
        """
        revision_id = _content_hash(payload)
        revision = ArtifactRevision(
            revision_id=revision_id,
            project_id=project_id,
            stage=stage,
            model_id=model_id,
            contract_version=contract_version,
            schema_version=schema_version,
            payload=payload,
        )
        key = self._cache_key(project_id, stage, model_id, contract_version)
        self._store.setdefault(key, []).append(revision)
        return revision

    # ── Read ───────────────────────────────────────────────────────────────────

    def latest(
        self,
        *,
        project_id: int,
        stage: str,
        model_id: str,
        contract_version: str,
    ) -> ArtifactRevision | None:
        """Return the most recent revision for the given key, or None on miss."""
        key = self._cache_key(project_id, stage, model_id, contract_version)
        revisions = self._store.get(key)
        return revisions[-1] if revisions else None

    def all_revisions(
        self,
        *,
        project_id: int,
        stage: str,
        model_id: str,
        contract_version: str,
    ) -> list[ArtifactRevision]:
        """Return all revisions for the given key, oldest first."""
        key = self._cache_key(project_id, stage, model_id, contract_version)
        return list(self._store.get(key, []))

    def hit(
        self,
        *,
        project_id: int,
        stage: str,
        model_id: str,
        contract_version: str,
    ) -> bool:
        """Return True if a cached revision exists for this key."""
        return self.latest(
            project_id=project_id,
            stage=stage,
            model_id=model_id,
            contract_version=contract_version,
        ) is not None

    # ── Near-duplicate detection ───────────────────────────────────────────────

    def is_near_duplicate(
        self,
        *,
        project_id: int,
        stage: str,
        model_id: str,
        contract_version: str,
        candidate_payload: dict[str, Any],
    ) -> bool:
        """Return True if the candidate payload content-hash matches the latest revision.

        This is the "same content, different run" detection used to avoid
        re-running expensive stages when the upstream artifact did not
        materially change.
        """
        latest = self.latest(
            project_id=project_id,
            stage=stage,
            model_id=model_id,
            contract_version=contract_version,
        )
        if latest is None:
            return False
        return latest.revision_id == _content_hash(candidate_payload)

    # ── Serialization ──────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of all revisions (for persistence)."""
        return {
            key: [
                {
                    **rev.to_dict(),
                    "payload": rev.payload,
                }
                for rev in revisions
            ]
            for key, revisions in self._store.items()
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Restore registry state from a snapshot dict."""
        self._store.clear()
        for key, revisions in snapshot.items():
            self._store[key] = [
                ArtifactRevision(
                    revision_id=r["revision_id"],
                    project_id=r["project_id"],
                    stage=r["stage"],
                    model_id=r["model_id"],
                    contract_version=r["contract_version"],
                    schema_version=r["schema_version"],
                    payload=r["payload"],
                    created_at=r.get("created_at", time.time()),
                )
                for r in revisions
            ]

    def stats(self) -> dict[str, int]:
        return {
            "total_keys": len(self._store),
            "total_revisions": sum(len(v) for v in self._store.values()),
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(
        project_id: int,
        stage: str,
        model_id: str,
        contract_version: str,
    ) -> str:
        return f"{project_id}:{stage}:{model_id}:{contract_version}"


# Module-level singleton for convenience; callers may also instantiate directly.
_default_registry: ArtifactRegistry | None = None


def get_registry() -> ArtifactRegistry:
    """Return the process-scoped default registry (created on first call)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ArtifactRegistry()
    return _default_registry
