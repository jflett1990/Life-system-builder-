"""
DocxBuilder — Generates a Word (.docx) document from Life System Builder pipeline data.

Structure:
  Cover metadata block       — system identity, life event, time horizon, audience
  Table of Contents          — Word TOC field (auto-updated when user opens file in Word)
  For each chapter (H1):
    Chapter narrative        — plain paragraph
    For each worksheet (H2):
      Worksheet descriptor   — plain paragraph (purpose text)
      For each field (H3 + blank lines) — fill-in space for user

Design choices:
  - Reads stage outputs directly from the dict returned by
    PipelineService.all_stage_outputs_as_dict(). No re-running the pipeline.
  - Uses built-in Word heading styles (Heading 1 / 2 / 3) so Word's TOC works.
  - Preserves document order from chapter_expansion; falls back to worksheet_system
    if chapter_expansion is absent (pre-chapter_expansion projects).
  - All worksheets render as simple label+blank-line sections regardless of
    layout type (table, checklist, two-column, form) — DOCX is for editing, not
    reproducing the exact print layout.
  - Writes to an io.BytesIO buffer — no filesystem writes.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from core.logging import get_logger

logger = get_logger(__name__)

_BLANK_LINE_COUNT = 2


def _add_toc_field(doc: Document) -> None:
    """Insert a Word TOC field at the current cursor position."""
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = paragraph.add_run()
    fld_char_begin = OxmlElement("w:fldChar")
    fld_char_begin.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = ' TOC \\o "1-3" \\h \\z \\u '
    fld_char_separate = OxmlElement("w:fldChar")
    fld_char_separate.set(qn("w:fldCharType"), "separate")
    fld_char_end = OxmlElement("w:fldChar")
    fld_char_end.set(qn("w:fldCharType"), "end")

    run._r.append(fld_char_begin)
    run._r.append(instr_text)
    run._r.append(fld_char_separate)
    run._r.append(fld_char_end)

    update_instruction = doc.add_paragraph()
    update_instruction.add_run(
        '(Right-click this area in Word and select "Update Field" to generate the Table of Contents.)'
    ).italic = True
    update_instruction.runs[0].font.size = Pt(9)
    update_instruction.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def _add_page_break(doc: Document) -> None:
    """Add a page break paragraph."""
    para = doc.add_paragraph()
    run = para.add_run()
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    run._r.append(br)


def _safe_text(value: Any, fallback: str = "") -> str:
    """Return a trimmed string from any value, or fallback if empty."""
    if not value:
        return fallback
    s = str(value).strip()
    return s if s else fallback


class DocxBuilder:
    """
    Accepts the dict of {stage_name: stage_output} returned by
    PipelineService.all_stage_outputs_as_dict() and produces a docx.Document
    serialised to bytes.
    """

    def build(self, project_id: int, all_outputs: dict[str, Any]) -> bytes:
        """
        Build the Word document and return it as raw bytes.

        Args:
            project_id:  Project ID (used for document_id formatting).
            all_outputs: Dict of stage_name → output dict for completed stages.

        Returns:
            Raw .docx bytes suitable for an HTTP attachment response.
        """
        doc = Document()
        self._set_default_styles(doc)

        arch = all_outputs.get("system_architecture", {})
        chapter_exp = all_outputs.get("chapter_expansion", {})
        ws_system = all_outputs.get("worksheet_system", {})

        system_name = _safe_text(arch.get("system_name"), "Operational Control System")
        life_event = _safe_text(arch.get("life_event"), "")
        system_objective = _safe_text(arch.get("system_objective"), "")
        time_horizon = _safe_text(arch.get("time_horizon"), "")
        audience = _safe_text(arch.get("audience"), "")
        document_id = f"LSB-{project_id:05d}"
        generated_date = date.today().strftime("%B %d, %Y")

        chapters: list[dict] = chapter_exp.get("chapters", [])
        legacy_worksheets: list[dict] = ws_system.get("worksheets", [])

        # ── Cover block ─────────────────────────────────────────────────────────
        doc.add_heading(system_name, level=0)

        cover_para = doc.add_paragraph()
        if life_event:
            cover_para.add_run(f"Life Event: {life_event}\n")
        if system_objective:
            cover_para.add_run(f"{system_objective}\n")
        if time_horizon:
            cover_para.add_run(f"Time Horizon: {time_horizon}\n")
        if audience:
            cover_para.add_run(f"Prepared For: {audience}\n")
        cover_para.add_run(f"Generated: {generated_date}  ·  Document ID: {document_id}")
        for run in cover_para.runs:
            run.font.size = Pt(10)

        doc.add_paragraph()

        # ── TOC field ────────────────────────────────────────────────────────────
        doc.add_heading("Table of Contents", level=1)
        _add_toc_field(doc)
        _add_page_break(doc)

        # ── Chapters ─────────────────────────────────────────────────────────────
        if chapters:
            total_worksheets = sum(len(ch.get("worksheets", [])) for ch in chapters)
            logger.debug(
                "DocxBuilder | project=%d | chapters=%d | worksheets=%d",
                project_id, len(chapters), total_worksheets,
            )
            for ch in chapters:
                ch_num = ch.get("chapter_number", chapters.index(ch) + 1)
                ch_title = _safe_text(ch.get("chapter_title"), f"Chapter {ch_num}")
                narrative = _safe_text(ch.get("narrative"), "")
                worksheets = ch.get("worksheets", [])

                doc.add_heading(f"Chapter {ch_num}: {ch_title}", level=1)

                if narrative:
                    doc.add_paragraph(narrative)

                quick_rules: list = ch.get("quick_reference_rules", [])
                if quick_rules:
                    doc.add_heading("Quick Reference Rules", level=2)
                    for rule in quick_rules:
                        rule_text = (
                            rule if isinstance(rule, str)
                            else rule.get("rule", rule.get("text", str(rule)))
                        )
                        if rule_text:
                            p = doc.add_paragraph(style="List Bullet")
                            p.add_run(_safe_text(rule_text))

                for ws in worksheets:
                    self._add_worksheet(doc, ws)

                _add_page_break(doc)

        elif legacy_worksheets:
            logger.debug(
                "DocxBuilder | project=%d | legacy path | worksheets=%d",
                project_id, len(legacy_worksheets),
            )
            for i, ws in enumerate(legacy_worksheets):
                title = _safe_text(ws.get("title"), f"Worksheet {i + 1}")
                purpose = _safe_text(ws.get("purpose"), "")
                doc.add_heading(title, level=1)
                if purpose:
                    doc.add_paragraph(purpose)
                self._add_worksheet(doc, ws)
                _add_page_break(doc)

        else:
            doc.add_paragraph(
                "No chapter content has been generated yet. "
                "Complete the Chapter Expansion pipeline stage to populate this document."
            )

        # ── Serialize to bytes ────────────────────────────────────────────────
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        raw = buf.read()
        logger.info(
            "DocxBuilder | project=%d | size=%d bytes",
            project_id, len(raw),
        )
        return raw

    def _add_worksheet(self, doc: Document, ws: dict) -> None:
        """
        Add a single worksheet section: H2 heading, purpose paragraph,
        then field prompts as H3 headings + blank fill-in lines.

        Layout routing:
          "form" / "two-column"  → sections[].section_title (bold) +
                                   sections[].fields[].label as H3 prompts
          "table"                → table_columns as H3 column-header prompts
          "checklist"            → checklist_items as H3 prompts
          legacy top-level fields (no sections)  → fields[].label as H3 prompts
          final fallback         → generic "Notes" H3
        """
        title   = _safe_text(ws.get("title"), "Worksheet")
        purpose = _safe_text(ws.get("purpose"), "")
        layout  = ws.get("layout", "form")

        doc.add_heading(title, level=2)

        if purpose:
            p = doc.add_paragraph(purpose)
            for run in p.runs:
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

        # ── Two-column header ─────────────────────────────────────────────────
        if layout == "two-column":
            left  = _safe_text(ws.get("left_column_label"),  "Current State")
            right = _safe_text(ws.get("right_column_label"), "Target State")
            doc.add_heading(f"{left}  /  {right}", level=3)

        # ── Table layout: column headers as fill-in rows ──────────────────────
        if layout == "table":
            columns: list[str] = ws.get("table_columns", [])
            row_count: int = ws.get("table_row_count", 12)
            if columns:
                for col in columns:
                    col_label = _safe_text(col, "")
                    if col_label:
                        doc.add_heading(col_label, level=3)
                        for _ in range(min(row_count, 6)):
                            doc.add_paragraph("_" * 60)
            else:
                doc.add_heading("Notes", level=3)
                for _ in range(_BLANK_LINE_COUNT):
                    doc.add_paragraph("_" * 60)
            return

        # ── Checklist layout: each item as a fill-in prompt ───────────────────
        if layout == "checklist":
            items: list = ws.get("checklist_items", [])
            if items:
                for item in items:
                    item_text = _safe_text(item if isinstance(item, str) else item.get("label", str(item)), "")
                    if item_text:
                        p = doc.add_paragraph(style="List Bullet")
                        p.add_run(item_text)
            else:
                doc.add_heading("Notes", level=3)
                for _ in range(_BLANK_LINE_COUNT):
                    doc.add_paragraph("_" * 60)
            return

        # ── Form / two-column: sections → fields ──────────────────────────────
        sections: list[dict] = ws.get("sections", [])
        if sections:
            for section in sections:
                section_title = _safe_text(section.get("section_title"), "")
                if section_title:
                    # Section title as a bold paragraph (not a heading level to
                    # avoid polluting the Word TOC with every section name).
                    sec_para = doc.add_paragraph()
                    run = sec_para.add_run(section_title)
                    run.bold = True
                    run.font.size = Pt(10)

                instructions = _safe_text(section.get("instructions"), "")
                if instructions:
                    ins_para = doc.add_paragraph(instructions)
                    for r in ins_para.runs:
                        r.font.size = Pt(9)
                        r.font.italic = True
                        r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

                fields: list[dict] = section.get("fields", [])
                if fields:
                    for field_item in fields:
                        label = _safe_text(
                            field_item.get("label") or
                            field_item.get("name") or
                            field_item.get("title"),
                            "",
                        )
                        if not label:
                            continue
                        doc.add_heading(label, level=3)
                        for _ in range(_BLANK_LINE_COUNT):
                            doc.add_paragraph("_" * 60)
                else:
                    # Section without fields — leave a generic write-in block
                    doc.add_heading(section_title or "Notes", level=3)
                    for _ in range(_BLANK_LINE_COUNT):
                        doc.add_paragraph("_" * 60)
            return

        # ── Legacy: top-level fields list (older stage outputs) ───────────────
        top_level_fields: list[dict] = ws.get("fields", [])
        if top_level_fields:
            for field_item in top_level_fields:
                label = _safe_text(
                    field_item.get("label") or
                    field_item.get("name") or
                    field_item.get("title"),
                    "",
                )
                if not label:
                    continue
                doc.add_heading(label, level=3)
                for _ in range(_BLANK_LINE_COUNT):
                    doc.add_paragraph("_" * 60)
            return

        # ── Final fallback ────────────────────────────────────────────────────
        doc.add_heading("Notes", level=3)
        for _ in range(_BLANK_LINE_COUNT):
            doc.add_paragraph("_" * 60)

    def _set_default_styles(self, doc: Document) -> None:
        """Adjust base font so the document looks clean out of the box."""
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(11)
