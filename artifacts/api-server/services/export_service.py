"""
ExportService — file packaging layer for Life System Builder.

Responsibilities:
  - Build in-memory zip bundles from rendered HTML + pipeline JSON
  - Expose per-format downloads (zip, html, per-stage json)
  - Provide a clear, honest hook point for future PDF rendering

Bundle structure:
  LSB-{id:05d}-export.zip
  ├── manifest.json          — bundle metadata + file index
  ├── html/
  │   └── document.html      — self-contained, print-ready HTML
  ├── json/
  │   ├── system_architecture.json
  │   ├── worksheet_system.json
  │   ├── layout_mapping.json
  │   ├── render_blueprint.json
  │   └── validation_audit.json   (present only if stage completed)
  └── pdf/
      └── PENDING.txt            — honest explanation, not a fake PDF

PDF hook:
  export_pdf() raises NotImplementedError with a clear message.
  The html/document.html is print-ready — browsers can print-to-PDF natively.
  When a server-side PDF renderer (WeasyPrint, Playwright, headless Chrome) is
  integrated, export_pdf() is the single method to implement.

Design:
  ExportService depends on RenderService (for HTML) and PipelineService (for JSON).
  ZipPackageBuilder is a pure in-memory utility — no filesystem writes, no temp files.
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.logging import get_logger
from services.render_service import RenderService, RenderServiceError
from services.pipeline_service import PipelineService

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ExportError(Exception):
    """Raised when an export cannot be completed."""


class ExportNotReadyError(ExportError):
    """Raised when the project has no completed stages to export."""


# ---------------------------------------------------------------------------
# Bundle manifest (what goes into manifest.json inside the zip)
# ---------------------------------------------------------------------------

@dataclass
class BundleManifest:
    """Structured metadata written as manifest.json inside the zip bundle."""
    bundle_id: str
    project_id: int
    document_id: str
    system_name: str
    life_event: str
    page_count: int
    stages_exported: list[str]
    created_at: str                         # ISO 8601 UTC
    bundle_version: str = "1.0"
    contents: dict[str, Any] = field(default_factory=dict)
    pdf_status: str = "not_implemented"
    pdf_note: str = (
        "PDF rendering is not yet integrated. "
        "The html/document.html file in this bundle is print-ready. "
        "To create a PDF: open it in any browser and use File → Print → Save as PDF. "
        "For headless generation: chromium --headless --print-to-pdf=output.pdf html/document.html"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "bundle_version": self.bundle_version,
            "project_id": self.project_id,
            "document_id": self.document_id,
            "system_name": self.system_name,
            "life_event": self.life_event,
            "page_count": self.page_count,
            "stages_exported": self.stages_exported,
            "created_at": self.created_at,
            "contents": self.contents,
            "pdf_status": self.pdf_status,
            "pdf_note": self.pdf_note,
        }


# ---------------------------------------------------------------------------
# PDF pending notice (written to pdf/PENDING.txt in the zip)
# ---------------------------------------------------------------------------

_PDF_PENDING_TEXT = """\
PDF EXPORT — NOT YET IMPLEMENTED
=================================

PDF generation has not been integrated into this version of Life System Builder.

THE HTML FILE IS PRINT-READY
-----------------------------
The file html/document.html in this bundle is fully self-contained and
designed for print output. To create a PDF from it:

  Browser (any OS):
    1. Open html/document.html in Chrome, Firefox, or Safari
    2. File → Print (Ctrl+P / Cmd+P)
    3. Select "Save as PDF" as the destination
    4. Set margins to "None" or "Minimum"
    5. Enable "Background graphics" if available

  Command line (headless Chrome):
    chromium --headless --print-to-pdf=output.pdf html/document.html

  Command line (WeasyPrint):
    weasyprint html/document.html output.pdf

FUTURE IMPLEMENTATION HOOK
---------------------------
When a server-side PDF renderer is integrated, ExportService.export_pdf()
is the single method that needs implementation. The HTML pipeline is already
producing the correct output — no content changes are required.

Candidate libraries:
  - WeasyPrint (Python, no browser required)
  - Playwright (headless Chromium, highest fidelity)
  - wkhtmltopdf (legacy, widely deployed)
"""


# ---------------------------------------------------------------------------
# ZipPackageBuilder — pure in-memory zip construction
# ---------------------------------------------------------------------------

class ZipPackageBuilder:
    """
    Builds an in-memory zip archive from structured export data.

    Usage:
        builder = ZipPackageBuilder()
        zip_bytes = builder.build(manifest, html, stage_outputs)
    """

    def build(
        self,
        manifest: BundleManifest,
        html: str,
        stage_outputs: dict[str, Any],
    ) -> bytes:
        """
        Build the zip archive and return it as raw bytes.

        Args:
            manifest:      BundleManifest to serialize as manifest.json.
            html:          Full rendered HTML string.
            stage_outputs: Dict of stage_name → output dict for each completed stage.

        Returns:
            Raw zip bytes — ready for a HTTP response body.
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # manifest.json
            zf.writestr(
                "manifest.json",
                json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
            )

            # html/document.html
            zf.writestr("html/document.html", html.encode("utf-8"))

            # json/{stage}.json — one file per completed stage
            for stage_name, output_data in stage_outputs.items():
                zf.writestr(
                    f"json/{stage_name}.json",
                    json.dumps(output_data, indent=2, ensure_ascii=False),
                )

            # pdf/PENDING.txt — honest PDF hook
            zf.writestr("pdf/PENDING.txt", _PDF_PENDING_TEXT)

        buf.seek(0)
        raw = buf.read()
        logger.debug(
            "ZipPackageBuilder | bundle_id=%s | stages=%d | size=%d bytes",
            manifest.bundle_id, len(stage_outputs), len(raw),
        )
        return raw


# ---------------------------------------------------------------------------
# ExportService
# ---------------------------------------------------------------------------

class ExportService:
    """
    File packaging layer for Life System Builder.

    Depends on:
      RenderService — renders HTML from pipeline stage outputs
      PipelineService — loads per-stage JSON outputs

    All methods are stateless across calls — safe to instantiate per-request.
    """

    def __init__(self, db: Session) -> None:
        self._render_svc = RenderService(db)
        self._pipeline = PipelineService(db)
        self._builder = ZipPackageBuilder()

    # ── Public API ────────────────────────────────────────────────────────────

    def export_zip(self, project_id: int) -> tuple[bytes, str]:
        """
        Build and return the full zip bundle for a project.

        Returns:
            (zip_bytes, filename) — filename is e.g. "LSB-00001-export.zip"

        Raises:
            ExportNotReadyError if no stages are complete.
            ExportError for render or packaging failures.
        """
        stage_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if not stage_outputs:
            raise ExportNotReadyError(
                f"Project {project_id} has no completed stages. "
                "Run at least the system_architecture stage before exporting."
            )

        try:
            render_result = self._render_svc.render(project_id)
        except RenderServiceError as e:
            raise ExportError(f"Render failed for project {project_id}: {e}") from e

        arch = stage_outputs.get("system_architecture", {})
        system_name = arch.get("system_name", "Operational Control System")
        life_event = arch.get("life_event", "")
        document_id = f"LSB-{project_id:05d}"
        now_utc = datetime.now(timezone.utc)
        created_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        bundle_id = f"{document_id}-{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
        stages_exported = sorted(stage_outputs.keys())

        manifest = BundleManifest(
            bundle_id=bundle_id,
            project_id=project_id,
            document_id=document_id,
            system_name=system_name,
            life_event=life_event,
            page_count=render_result.page_count,
            stages_exported=stages_exported,
            created_at=created_at,
            contents={
                "manifest": "manifest.json",
                "html": "html/document.html",
                "json_stages": {
                    stage: f"json/{stage}.json" for stage in stages_exported
                },
                "pdf": "pdf/PENDING.txt",
            },
        )

        zip_bytes = self._builder.build(manifest, render_result.html, stage_outputs)
        filename = f"{document_id}-export.zip"

        logger.info(
            "ExportService.export_zip | project=%d | bundle_id=%s | stages=%d | size=%d B",
            project_id, bundle_id, len(stages_exported), len(zip_bytes),
        )
        return zip_bytes, filename

    def export_html(self, project_id: int) -> tuple[str, str]:
        """
        Return the rendered HTML document and a suggested filename.

        Returns:
            (html_content: str, filename: str)

        Raises:
            ExportNotReadyError / ExportError.
        """
        stage_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if not stage_outputs:
            raise ExportNotReadyError(
                f"Project {project_id} has no completed stages."
            )

        try:
            render_result = self._render_svc.render(project_id)
        except RenderServiceError as e:
            raise ExportError(str(e)) from e

        filename = f"LSB-{project_id:05d}-document.html"
        logger.info(
            "ExportService.export_html | project=%d | page_count=%d | len=%d",
            project_id, render_result.page_count, len(render_result.html),
        )
        return render_result.html, filename

    def export_stage_json(self, project_id: int, stage: str) -> tuple[str, str]:
        """
        Return the JSON output for a single stage as a formatted string.

        Args:
            project_id: Project ID.
            stage:      Stage name (underscores — e.g. "system_architecture").

        Returns:
            (json_str: str, filename: str)

        Raises:
            ExportNotReadyError if the stage is not complete.
        """
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if stage not in all_outputs:
            raise ExportNotReadyError(
                f"Stage '{stage}' is not complete for project {project_id}."
            )
        filename = f"LSB-{project_id:05d}-{stage}.json"
        json_str = json.dumps(all_outputs[stage], indent=2, ensure_ascii=False)
        return json_str, filename

    def export_all_json(self, project_id: int) -> tuple[str, str]:
        """
        Return all stage outputs as a single combined JSON object.

        Returns:
            (json_str: str, filename: str)
        """
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if not all_outputs:
            raise ExportNotReadyError(
                f"Project {project_id} has no completed stages."
            )
        combined = {
            "project_id": project_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "stages": all_outputs,
        }
        filename = f"LSB-{project_id:05d}-all-stages.json"
        return json.dumps(combined, indent=2, ensure_ascii=False), filename

    def bundle_manifest_info(self, project_id: int) -> dict[str, Any]:
        """
        Return bundle manifest metadata without building the zip.

        Useful for the /manifest API endpoint — shows what would be in the bundle.
        Raises ExportNotReadyError if no stages are complete.
        """
        stage_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        if not stage_outputs:
            raise ExportNotReadyError(
                f"Project {project_id} has no completed stages."
            )

        arch = stage_outputs.get("system_architecture", {})
        system_name = arch.get("system_name", "Operational Control System")
        life_event = arch.get("life_event", "")
        document_id = f"LSB-{project_id:05d}"
        now_utc = datetime.now(timezone.utc)
        created_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        bundle_id = f"{document_id}-{now_utc.strftime('%Y%m%dT%H%M%SZ')}"
        stages_exported = sorted(stage_outputs.keys())

        manifest = BundleManifest(
            bundle_id=bundle_id,
            project_id=project_id,
            document_id=document_id,
            system_name=system_name,
            life_event=life_event,
            page_count=0,       # page_count requires a render pass; omit here
            stages_exported=stages_exported,
            created_at=created_at,
            contents={
                "manifest": "manifest.json",
                "html": "html/document.html",
                "json_stages": {
                    stage: f"json/{stage}.json" for stage in stages_exported
                },
                "pdf": "pdf/PENDING.txt",
            },
        )
        info = manifest.to_dict()
        info["_note"] = (
            "page_count is 0 in this preview — it is computed during full render. "
            "Download /download to get the full bundle with an accurate page_count."
        )
        return info

    def export_pdf(self, project_id: int) -> bytes:
        """
        PDF export — NOT YET IMPLEMENTED.

        Future implementation hook. When a PDF renderer is integrated
        (WeasyPrint, Playwright, or headless Chrome), this method should:

          1. Call self._render_svc.render(project_id) to get the HTML string
          2. Pass the HTML to the renderer and receive PDF bytes
          3. Return raw PDF bytes

        The html/document.html in the zip bundle is print-ready and
        can be used as input to any headless browser PDF generator without
        any HTML modifications.
        """
        raise NotImplementedError(
            "PDF export is not yet implemented. "
            "Use the HTML export — it is print-ready and can be saved as PDF "
            "from any browser using File → Print → Save as PDF. "
            "See pdf/PENDING.txt in the zip bundle for full instructions."
        )
