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
import tempfile
import os
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
# Playwright PDF renderer (async helper — called via asyncio.run)
# ---------------------------------------------------------------------------

async def _render_pdf_with_playwright(html: str, timeout_ms: int = 60_000) -> bytes:
    """
    Render *html* to PDF bytes using Playwright headless Chromium.

    Writes the HTML to a temporary file, loads it via file:// URL, waits for
    Pagedjs to finish pagination (signalled by window.__lsb_pdf_ready), then
    calls page.pdf() with US Letter format and background graphics enabled.

    Args:
        html:       Complete HTML document string.
        timeout_ms: Maximum time to wait for Pagedjs to finish (default 60 s).

    Returns:
        Raw PDF bytes.

    Raises:
        ExportError on Playwright launch/timeout failure.
    """
    from playwright.async_api import async_playwright, Error as PlaywrightError
    # Import here to avoid circular; ExportError is defined later in this module
    # We re-raise as a plain RuntimeError here; callers wrap to ExportError.

    tmp_path = None
    try:
        # Write HTML to a temp file so Pagedjs can load external resources via file://
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html)
            tmp_path = f.name

        file_url = f"file://{tmp_path}"

        # Prefer the Nix-managed system Chromium (which has correct library linkage)
        # over Playwright's bundled chromium-headless-shell (which lacks system libs).
        import shutil
        system_chromium = shutil.which("chromium") or shutil.which("chromium-browser")

        async with async_playwright() as pw:
            launch_kwargs: dict = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-dev-shm-usage"],
            }
            if system_chromium:
                launch_kwargs["executable_path"] = system_chromium

            browser = await pw.chromium.launch(**launch_kwargs)
            page = await browser.new_page()

            # Navigate and wait for network to be idle (Pagedjs CDN load)
            try:
                await page.goto(file_url, wait_until="networkidle", timeout=timeout_ms)
            except PlaywrightError:
                # networkidle may not fire for file:// — fallback to domcontentloaded
                await page.goto(file_url, wait_until="domcontentloaded", timeout=timeout_ms)

            # Wait for Pagedjs to signal completion via window.__lsb_pdf_ready.
            # The injected script uses a MutationObserver on #lsb-loading removal
            # and a 8-second fallback — so the signal will fire within ~8 seconds
            # regardless of whether Pagedjs actually completed.
            try:
                await page.wait_for_function(
                    "window.__lsb_pdf_ready === true",
                    timeout=15_000,  # 15s: longer than the 8s fallback in the injected script
                )
            except PlaywrightError:
                # Signal never fired — generate PDF from current render state
                logger.warning(
                    "_render_pdf_with_playwright | Ready signal not received within 15s — "
                    "generating PDF from current render state",
                )

            pdf_bytes = await page.pdf(
                format="Letter",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            await browser.close()
            return pdf_bytes

    except Exception as exc:
        raise RuntimeError(f"Playwright PDF render failed: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


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
        pdf_bytes: bytes | None = None,
    ) -> bytes:
        """
        Build the zip archive and return it as raw bytes.

        Args:
            manifest:      BundleManifest to serialize as manifest.json.
            html:          Full rendered HTML string.
            stage_outputs: Dict of stage_name → output dict for each completed stage.
            pdf_bytes:     Optional PDF bytes. If provided, included as pdf/document.pdf.
                           If None, falls back to pdf/PENDING.txt.

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

            # pdf/document.pdf or pdf/PENDING.txt fallback
            if pdf_bytes:
                zf.writestr("pdf/document.pdf", pdf_bytes)
            else:
                zf.writestr("pdf/PENDING.txt", _PDF_PENDING_TEXT)

        buf.seek(0)
        raw = buf.read()
        logger.debug(
            "ZipPackageBuilder | bundle_id=%s | stages=%d | pdf=%s | size=%d bytes",
            manifest.bundle_id, len(stage_outputs),
            "yes" if pdf_bytes else "pending", len(raw),
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

        # Attempt to generate PDF — fall back gracefully if it fails
        pdf_bytes: bytes | None = None
        try:
            pdf_bytes = self.export_pdf(project_id)
            pdf_path = "pdf/document.pdf"
        except (ExportError, ExportNotReadyError) as e:
            logger.warning(
                "ExportService.export_zip | PDF generation failed (falling back to PENDING.txt): %s", e
            )
            pdf_path = "pdf/PENDING.txt"

        manifest = BundleManifest(
            bundle_id=bundle_id,
            project_id=project_id,
            document_id=document_id,
            system_name=system_name,
            life_event=life_event,
            page_count=render_result.page_count,
            stages_exported=stages_exported,
            created_at=created_at,
            pdf_status="ready" if pdf_bytes else "not_implemented",
            pdf_note=(
                "PDF is included as pdf/document.pdf in this bundle."
                if pdf_bytes
                else (
                    "PDF rendering failed during zip build. "
                    "The html/document.html file in this bundle is print-ready. "
                    "Open it in any browser and use File → Print → Save as PDF."
                )
            ),
            contents={
                "manifest": "manifest.json",
                "html": "html/document.html",
                "json_stages": {
                    stage: f"json/{stage}.json" for stage in stages_exported
                },
                "pdf": pdf_path,
            },
        )

        zip_bytes = self._builder.build(manifest, render_result.html, stage_outputs, pdf_bytes)
        filename = f"{document_id}-export.zip"

        logger.info(
            "ExportService.export_zip | project=%d | bundle_id=%s | stages=%d | pdf=%s | size=%d B",
            project_id, bundle_id, len(stages_exported),
            "yes" if pdf_bytes else "pending", len(zip_bytes),
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
        Render the project to PDF using Playwright headless Chromium.

        Steps:
          1. Render the HTML via RenderService
          2. Write HTML to a temporary file
          3. Launch headless Chromium via Playwright
          4. Wait for Pagedjs to finish (afterRendered callback sets window.__lsb_ready)
          5. Call page.pdf() with US Letter, background graphics, no extra margins
          6. Return raw PDF bytes

        Raises:
          ExportNotReadyError — if no stages are complete
          ExportError — if Playwright fails or times out
        """
        import asyncio

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

        html = render_result.html

        # Inject a signal: watch for removal of #lsb-loading (which Pagedjs removes via
        # hideLoading() in afterRendered) OR set directly if Pagedjs fails to load.
        # We also set a fallback polling timeout so the PDF generation proceeds even
        # if Pagedjs CDN is unreachable from the headless context.
        signal_patch = """
<script>
(function() {
  // Signal that PDF rendering is ready — either after Pagedjs finishes or on fallback.
  function signalReady() {
    if (!window.__lsb_pdf_ready) {
      window.__lsb_pdf_ready = true;
    }
  }

  // Watch for #lsb-loading element removal (Pagedjs calls hideLoading on completion)
  var observer = new MutationObserver(function() {
    if (!document.getElementById('lsb-loading')) {
      observer.disconnect();
      signalReady();
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  // Fallback: if Pagedjs never starts or takes too long, signal after 8 seconds
  setTimeout(signalReady, 8000);
})();
</script>"""

        # Insert signal patch at the very start of <body> (before any Pagedjs scripts fire)
        if "<body>" in html:
            html = html.replace("<body>", "<body>\n" + signal_patch, 1)
        elif "</head>" in html:
            html = html.replace("</head>", signal_patch + "\n</head>", 1)

        try:
            pdf_bytes = asyncio.run(_render_pdf_with_playwright(html))
        except RuntimeError as e:
            raise ExportError(str(e)) from e

        logger.info(
            "ExportService.export_pdf | project=%d | size=%d B",
            project_id, len(pdf_bytes),
        )
        return pdf_bytes
