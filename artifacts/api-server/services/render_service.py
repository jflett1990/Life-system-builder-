"""
RenderService — produces HTML from validated pipeline outputs.

Delegates render artifact persistence to RenderArtifactRepository.

Flow:
  1. Load all completed stage outputs for a project
  2. Extract theme tokens from render_blueprint (or use defaults)
  3. ManifestBuilder maps outputs → RenderManifest (ordered page list)
  4. Renderer iterates manifest → Jinja2 → single self-contained HTML string
  5. Persist RenderArtifact (manifest_json + page_count) via repository
  6. Return RenderResult / ExportBundle to the API layer

No LLM calls. No content decisions. Pure structured-data → HTML transformation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.logging import get_logger
from models.render_artifact import RenderArtifact
from render.manifest_builder import ManifestBuilder
from render.geometry_validator import probe_layout
from render.validation_report import ValidationReport, merge_geometry_probe
from render.renderer import Renderer, RendererError
from repositories.render_repo import RenderArtifactRepository
from schemas.render import RenderResult, ExportBundle
from services.pipeline_service import PipelineService

logger = get_logger(__name__)


class RenderServiceError(Exception):
    pass


class RenderService:
    def __init__(self, db: Any) -> None:
        self._pipeline = PipelineService(db)
        self._render_repo = RenderArtifactRepository(db)
        self._manifest_builder = ManifestBuilder()
        self._renderer = Renderer()

    # ── Public API ─────────────────────────────────────────────────────────────

    def render(self, project_id: int) -> RenderResult:
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if not all_outputs:
            raise RenderServiceError(
                f"No completed stages found for project {project_id}. "
                "Run at least the system_architecture stage before rendering."
            )

        theme_tokens = self._extract_theme_tokens(all_outputs)
        manifest = self._manifest_builder.build(project_id, all_outputs, theme_tokens)

        validation = manifest.validation_report or {}
        if validation.get("build_status") == "fail":
            raise RenderServiceError(f"Render validation failed: {validation.get('errors', [])}")

        try:
            html = self._renderer.render(manifest)
        except RendererError as e:
            raise RenderServiceError(str(e)) from e

        # Stage 6: physical pagination probe (post-paged layout diagnostics).
        # Merges real geometry findings (overflow/split headers/orphans) into the
        # structural validation report before persistence/export.
        geometry_probe = probe_layout(html)
        merged_validation = merge_geometry_probe(
            ValidationReport(
                build_status=validation.get("build_status", "pass"),
                errors=validation.get("errors", []),
                warnings=validation.get("warnings", []),
                stats=validation.get("stats", {}),
            ),
            geometry_probe.to_dict(),
        ).to_dict()

        if merged_validation.get("build_status") == "fail":
            raise RenderServiceError(f"Render geometry validation failed: {merged_validation.get('errors', [])}")

        manifest.validation_report = merged_validation
        self._persist_artifact(project_id, manifest, page_count=manifest.page_count)

        logger.info(
            "Rendered %d pages for project %d (document_id=%s)",
            manifest.page_count, project_id, manifest.document_id,
        )
        return RenderResult(
            project_id=project_id,
            html=html,
            page_count=manifest.page_count,
            validation_report=merged_validation,
        )

    def export(self, project_id: int) -> ExportBundle:
        render_result = self.render(project_id)
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        return ExportBundle(
            project_id=project_id,
            html=render_result.html,
            stages_json=all_outputs,
            exported_at=datetime.now(timezone.utc),
            validation_report=render_result.validation_report,
        )

    def render_page_preview(self, project_id: int, page_id: str) -> str:
        """Return HTML for a single page in isolation — for frontend preview panels."""
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if not all_outputs:
            raise RenderServiceError(f"No outputs for project {project_id}")

        theme_tokens = self._extract_theme_tokens(all_outputs)
        manifest = self._manifest_builder.build(project_id, all_outputs, theme_tokens)

        try:
            return self._renderer.render_page_preview(manifest, page_id)
        except RendererError as e:
            raise RenderServiceError(str(e)) from e

    def get_manifest(self, project_id: int) -> dict:
        """Return the render manifest as a JSON-serialisable dict (for debugging/API)."""
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if not all_outputs:
            raise RenderServiceError(f"No outputs for project {project_id}")

        theme_tokens = self._extract_theme_tokens(all_outputs)
        manifest = self._manifest_builder.build(project_id, all_outputs, theme_tokens)

        return {
            "document_id": manifest.document_id,
            "document_title": manifest.document_title,
            "system_name": manifest.system_name,
            "page_count": manifest.page_count,
            "pages": [
                {
                    "page_id": p.page_id,
                    "sequence": p.sequence,
                    "archetype": p.archetype,
                    "page_break": p.page_break,
                    "estimated_height_px": p.estimated_height_px,
                    "overflow_risk": p.overflow_risk,
                }
                for p in manifest.pages
            ],
            "validation_report": manifest.validation_report,
            "layout_report": manifest.layout_report,
        }

    def get_layout_report(self, project_id: int) -> dict:
        """Build the manifest and return the layout report without rendering HTML.

        This is a lightweight call — no Playwright, no HTML generation.
        Suitable for surfacing geometry health in the UI during pipeline execution.
        """
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if not all_outputs:
            raise RenderServiceError(f"No outputs for project {project_id}")

        theme_tokens = self._extract_theme_tokens(all_outputs)
        manifest = self._manifest_builder.build(project_id, all_outputs, theme_tokens)

        from validators.layout_safety import validate_layout_safety
        safety = validate_layout_safety(manifest)

        return {
            "project_id": project_id,
            "document_id": manifest.document_id,
            "page_count": manifest.page_count,
            "layout_report": manifest.layout_report,
            "safety": safety.to_dict(),
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    def _persist_artifact(self, project_id: int, manifest: Any, page_count: int) -> None:
        """Upsert the RenderArtifact row for this project."""
        now = datetime.now(timezone.utc)
        row = self._render_repo.find_by_project(project_id)
        manifest_dict = {
            "document_id": manifest.document_id,
            "document_title": manifest.document_title,
            "system_name": manifest.system_name,
            "page_count": page_count,
            "validation_report": manifest.validation_report,
        }

        if row:
            row.set_manifest(manifest_dict)
            row.page_count = page_count
            row.updated_at = now
            self._render_repo.save(row)
        else:
            row = RenderArtifact(
                project_id=project_id,
                page_count=page_count,
                created_at=now,
                updated_at=now,
            )
            row.set_manifest(manifest_dict)
            self._render_repo.insert(row)

    def _extract_theme_tokens(self, all_outputs: dict[str, Any]) -> dict[str, str]:
        """
        Pull theme overrides from the render_blueprint stage output.
        Falls back to the system defaults defined in tokens.css for any missing key.
        """
        blueprint = all_outputs.get("render_blueprint", {})
        theme = blueprint.get("theme", {})
        palette = theme.get("color_palette", {})
        typography = theme.get("typography", {})
        spacing = theme.get("spacing", {})

        tokens: dict[str, str] = {}

        if palette.get("primary"):
            # --color-primary is the canonical variable used by cover + section
            # divider templates.  --color-cover-bg and --color-divider-bg are
            # kept as aliases so older saved renders remain visually correct.
            tokens["--color-primary"]     = palette["primary"]
            tokens["--color-cover-bg"]    = palette["primary"]
            tokens["--color-divider-bg"]  = palette["primary"]
            tokens["--color-chapter-bar"] = palette["primary"]
        if palette.get("accent"):
            tokens["--color-accent"] = palette["accent"]
        if palette.get("text_primary"):
            tokens["--color-text-primary"] = palette["text_primary"]
        if typography.get("heading_font"):
            tokens["--font-heading"] = typography["heading_font"]
        if typography.get("body_font"):
            tokens["--font-body"] = typography["body_font"]
        if typography.get("base_size_px"):
            tokens["--text-base"] = f"{typography['base_size_px']}px"
        if spacing.get("field_gap_px"):
            tokens["--field-gap"] = f"{spacing['field_gap_px']}px"

        return tokens
