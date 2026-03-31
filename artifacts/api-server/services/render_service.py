"""
RenderService — produces HTML from validated pipeline outputs.
Uses Jinja2 templates + CSS token injection from the render_blueprint.
No LLM calls — pure rendering from structured data.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.logging import get_logger
from schemas.render import RenderResult, ExportBundle
from services.pipeline_service import PipelineService

from datetime import datetime, timezone

logger = get_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "render" / "templates"


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


class RenderError(Exception):
    pass


class RenderService:
    def __init__(self, db: Any) -> None:
        self._pipeline = PipelineService(db)
        self._jinja = _get_jinja_env()

    def render(self, project_id: int) -> RenderResult:
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if not all_outputs:
            raise RenderError(f"No completed stages found for project {project_id}")

        theme_tokens = self._extract_theme_tokens(all_outputs)
        sections = self._build_sections(all_outputs)

        try:
            template = self._jinja.get_template("base.html")
        except Exception as e:
            raise RenderError(f"Base template not found: {e}") from e

        html = template.render(
            all_outputs=all_outputs,
            sections=sections,
            theme_tokens=theme_tokens,
            system=all_outputs.get("system_architecture", {}),
            worksheets=all_outputs.get("worksheet_system", {}).get("worksheets", []),
            layout=all_outputs.get("layout_mapping", {}),
            blueprint=all_outputs.get("render_blueprint", {}),
        )

        page_count = len(sections)
        logger.info("Rendered %d sections for project %d", page_count, project_id)
        return RenderResult(project_id=project_id, html=html, page_count=page_count)

    def export(self, project_id: int) -> ExportBundle:
        render_result = self.render(project_id)
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        return ExportBundle(
            project_id=project_id,
            html=render_result.html,
            stages_json=all_outputs,
            exported_at=datetime.now(timezone.utc),
        )

    def _extract_theme_tokens(self, all_outputs: dict[str, Any]) -> dict[str, str]:
        blueprint = all_outputs.get("render_blueprint", {})
        theme = blueprint.get("theme", {})
        palette = theme.get("color_palette", {})
        typography = theme.get("typography", {})
        spacing = theme.get("spacing", {})

        return {
            "--color-primary":      palette.get("primary", "#1a1a2e"),
            "--color-secondary":    palette.get("secondary", "#16213e"),
            "--color-accent":       palette.get("accent", "#0f3460"),
            "--color-background":   palette.get("background", "#ffffff"),
            "--color-surface":      palette.get("surface", "#f8f9fa"),
            "--color-text-primary": palette.get("text_primary", "#212529"),
            "--color-text-secondary": palette.get("text_secondary", "#6c757d"),
            "--color-border":       palette.get("border", "#dee2e6"),
            "--font-heading":       typography.get("heading_font", "Georgia, serif"),
            "--font-body":          typography.get("body_font", "Arial, sans-serif"),
            "--font-mono":          typography.get("mono_font", "Courier New, monospace"),
            "--font-size-base":     f"{typography.get('base_size_px', 14)}px",
            "--line-height-base":   str(typography.get("line_height", 1.6)),
            "--spacing-page-margin": f"{spacing.get('page_margin_mm', 20)}mm",
            "--spacing-section-gap": f"{spacing.get('section_gap_px', 48)}px",
            "--spacing-field-gap":   f"{spacing.get('field_gap_px', 16)}px",
        }

    def _build_sections(self, all_outputs: dict[str, Any]) -> list[dict]:
        sections = []

        arch = all_outputs.get("system_architecture")
        if arch:
            sections.append({"type": "system_architecture", "data": arch})

        ws = all_outputs.get("worksheet_system")
        if ws:
            for worksheet in ws.get("worksheets", []):
                sections.append({"type": "worksheet", "data": worksheet})

        layout = all_outputs.get("layout_mapping")
        if layout:
            sections.append({"type": "layout_mapping", "data": layout})

        blueprint = all_outputs.get("render_blueprint")
        if blueprint:
            sections.append({"type": "render_blueprint", "data": blueprint})

        return sections
