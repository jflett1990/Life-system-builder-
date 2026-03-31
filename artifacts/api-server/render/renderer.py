"""
Renderer — takes a RenderManifest and produces a fully self-contained HTML string.

Uses a Jinja2 Environment with:
  - Loader root:  render/           (so styles/ and templates/ are both accessible)
  - Autoescape:   HTML files only   (CSS files pass through raw)
  - Undefined:    ChainableUndefined (fails silently on missing keys → empty string)

The rendered HTML inlines all CSS and is suitable for:
  - Browser preview
  - Print-to-PDF via browser print dialog
  - wkhtmltopdf / headless Chrome
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import (
    ChainableUndefined,
    Environment,
    FileSystemLoader,
    select_autoescape,
)

from render.manifest_builder import RenderManifest

RENDER_DIR = Path(__file__).parent


def _build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(RENDER_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html",)),
        undefined=ChainableUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


_ENV: Environment | None = None


def _get_env() -> Environment:
    global _ENV
    if _ENV is None:
        _ENV = _build_env()
    return _ENV


class RendererError(Exception):
    pass


class Renderer:
    def __init__(self) -> None:
        self._env = _get_env()

    def render(self, manifest: RenderManifest) -> str:
        try:
            template = self._env.get_template("templates/_document.html")
        except Exception as e:
            raise RendererError(f"Document template not found: {e}") from e

        try:
            html = template.render(manifest=manifest)
        except Exception as e:
            raise RendererError(f"Template rendering failed: {e}") from e

        return html

    def render_page_preview(self, manifest: RenderManifest, page_id: str) -> str:
        """Render a single page in isolation, wrapped in a minimal HTML shell."""
        page = next((p for p in manifest.pages if p.page_id == page_id), None)
        if page is None:
            raise RendererError(f"Page '{page_id}' not found in manifest")

        single_page_manifest = RenderManifest(
            document_id=manifest.document_id,
            document_title=manifest.document_title,
            system_name=manifest.system_name,
            theme_tokens=manifest.theme_tokens,
            pages=[page],
        )
        return self.render(single_page_manifest)
