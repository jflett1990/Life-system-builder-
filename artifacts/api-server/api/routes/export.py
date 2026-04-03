"""
Export routes — file download and bundle packaging endpoints.

Route inventory:
  GET /{project_id}              — JSON metadata bundle (backward compat; used by frontend)
  GET /{project_id}/download     — full zip bundle download (html + json + manifest + pdf)
  GET /{project_id}/pdf          — PDF document only, as a downloadable file
  GET /{project_id}/html         — HTML document only, as a downloadable file
  GET /{project_id}/json         — combined JSON of all stages as a downloadable file
  GET /{project_id}/json/{stage} — single stage JSON as a downloadable file
  GET /{project_id}/manifest     — export bundle manifest as JSON (no file content)

PDF:
  PDF export is implemented via Playwright headless Chromium.
  GET /{project_id}/pdf returns application/pdf with Content-Disposition: attachment.
  Falls back gracefully with a 503 if Playwright fails or times out.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from schemas.render import ExportBundle
from services.render_service import RenderService, RenderServiceError
from services.export_service import ExportService, ExportError, ExportNotReadyError
from storage.database import get_db

router = APIRouter(prefix="/export", tags=["export"])


# ── Dependency factories ──────────────────────────────────────────────────────

def _render_svc(db: Session = Depends(get_db)) -> RenderService:
    return RenderService(db)


def _export_svc(db: Session = Depends(get_db)) -> ExportService:
    return ExportService(db)


# ── Existing endpoint — kept for frontend compatibility ───────────────────────

@router.get("/{project_id}", response_model=ExportBundle)
def export_project(
    project_id: int,
    svc: RenderService = Depends(_render_svc),
):
    """
    Return the full export bundle as JSON — HTML string + stages JSON dict.

    This is the primary endpoint used by the frontend ExportPage.
    It returns the rendered HTML and all stage outputs in a single JSON payload,
    which the client uses to offer browser-side file downloads.
    """
    try:
        return svc.export(project_id)
    except RenderServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── File download endpoints ───────────────────────────────────────────────────

@router.get("/{project_id}/download")
def download_bundle(
    project_id: int,
    svc: ExportService = Depends(_export_svc),
) -> Response:
    """
    Download the complete export bundle as a zip file.

    Bundle contents:
      manifest.json          — bundle metadata and file index
      html/document.html     — self-contained, print-ready HTML document
      json/{stage}.json      — one file per completed pipeline stage
      pdf/PENDING.txt        — PDF instructions (PDF rendering not yet implemented)

    Returns 400 if no pipeline stages have been completed.
    """
    try:
        zip_bytes, filename = svc.export_zip(project_id)
    except ExportNotReadyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )


@router.get("/{project_id}/pdf")
def download_pdf(
    project_id: int,
    svc: ExportService = Depends(_export_svc),
) -> Response:
    """
    Generate and download the project as a PDF file.

    Uses Playwright headless Chromium to render the print-ready HTML document
    (including Pagedjs pagination) and return a PDF with US Letter format and
    background graphics enabled.

    Generation takes 10–60 seconds for large documents.

    Returns:
      200 application/pdf with Content-Disposition: attachment on success.
      400 if no pipeline stages have been completed.
      503 if PDF generation fails (Playwright error or timeout).
    """
    try:
        pdf_bytes = svc.export_pdf(project_id)
    except ExportNotReadyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"PDF generation failed: {e}. Try downloading the HTML and printing to PDF from your browser.",
        )

    filename = f"LSB-{project_id:05d}-document.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@router.get("/{project_id}/html")
def download_html(
    project_id: int,
    svc: ExportService = Depends(_export_svc),
) -> Response:
    """
    Download the rendered HTML document as a standalone file.

    The HTML file is self-contained (styles embedded) and print-ready.
    Print to PDF from any browser using File → Print → Save as PDF.

    Returns 400 if the render step has not been completed.
    """
    try:
        html_content, filename = svc.export_html(project_id)
    except ExportNotReadyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(
        content=html_content.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{project_id}/json")
def download_all_json(
    project_id: int,
    svc: ExportService = Depends(_export_svc),
) -> Response:
    """
    Download all completed stage outputs as a single combined JSON file.

    Format:
      {
        "project_id": 1,
        "exported_at": "...",
        "stages": { "system_architecture": {...}, ... }
      }

    Returns 400 if no stages are complete.
    """
    try:
        json_str, filename = svc.export_all_json(project_id)
    except ExportNotReadyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(
        content=json_str.encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{project_id}/json/{stage}")
def download_stage_json(
    project_id: int,
    stage: str,
    svc: ExportService = Depends(_export_svc),
) -> Response:
    """
    Download a single stage's output as a JSON file.

    Stage names: system_architecture, worksheet_system, layout_mapping,
                 render_blueprint, validation_audit

    Returns 400 if the requested stage has not been completed.
    """
    try:
        json_str, filename = svc.export_stage_json(project_id, stage)
    except ExportNotReadyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(
        content=json_str.encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{project_id}/docx")
def download_docx(
    project_id: int,
    svc: ExportService = Depends(_export_svc),
) -> Response:
    """
    Generate and download the project as an editable Word document (.docx).

    The document uses proper Word heading styles (Heading 1/2/3) so Word's
    built-in Table of Contents generation works. Worksheets render as label +
    blank fill-in lines — suitable for personal editing and customisation.

    Generation is fast (< 1 second) since no HTML render pass is required.

    Returns:
      200 application/vnd.openxmlformats-officedocument.wordprocessingml.document
      400 if no pipeline stages have been completed.
      500 if the DOCX build fails.
    """
    try:
        docx_bytes, filename = svc.export_docx(project_id)
    except ExportNotReadyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(docx_bytes)),
        },
    )


@router.get("/{project_id}/manifest")
def get_export_manifest(
    project_id: int,
    svc: ExportService = Depends(_export_svc),
):
    """
    Return the export bundle manifest as JSON — no file content included.

    Contains: bundle_id, document_id, system_name, stages_exported,
              file paths index, pdf_status.

    Useful for checking what a bundle would contain before downloading.
    Returns 400 if no stages are complete.
    """
    try:
        return svc.bundle_manifest_info(project_id)
    except ExportNotReadyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExportError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Contracts (kept from original) ───────────────────────────────────────────

@router.get("/{project_id}/contracts", tags=["contracts"])
def list_contracts(project_id: int):
    from core.contract_registry import get_registry
    registry = get_registry()
    return {"contracts": registry.summary()}
