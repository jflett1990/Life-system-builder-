from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from render.document_model import FRONT_MATTER_SEQUENCE, ManualDocument
from render.composition_engine import ComposedDocument


@dataclass
class ValidationReport:
    build_status: str
    errors: list[str]
    warnings: list[str]
    stats: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "build_status": self.build_status,
            "errors": self.errors,
            "warnings": self.warnings,
            "stats": self.stats,
        }


def validate_manual(manual: ManualDocument, composed: ComposedDocument) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    id_set: set[str] = set()
    for d in manual.domains:
        if d.id in id_set:
            errors.append(f"Duplicate ID: {d.id}")
        id_set.add(d.id)
    for c in manual.chapters:
        if c.id in id_set:
            errors.append(f"Duplicate ID: {c.id}")
        id_set.add(c.id)
    for w in manual.worksheets:
        if w.id in id_set:
            errors.append(f"Duplicate ID: {w.id}")
        id_set.add(w.id)

    fm_ids = [entry.get("id") for entry in manual.front_matter]
    if fm_ids[: len(FRONT_MATTER_SEQUENCE)] != FRONT_MATTER_SEQUENCE:
        errors.append("Front matter order is not locked to required sequence")

    chapter_ids = {c.id for c in manual.chapters}
    for w in manual.worksheets:
        if w.chapter_ref not in chapter_ids:
            errors.append(f"Worksheet {w.id} references missing chapter {w.chapter_ref}")

    contents_count = len([p for p in composed.pages if p.page_class == "chapter_opener"])
    if contents_count != len(manual.chapters):
        errors.append("Chapter count mismatch between composition and model")

    worksheet_pages = len([p for p in composed.pages if p.page_class == "worksheet_page"])
    if worksheet_pages != len(manual.worksheets):
        errors.append("Worksheet count mismatch between model and rendered pages")

    orphan_headings = 0
    split_tables = 0
    overflow_blocks = 0
    for page in composed.pages:
        if page.page_class == "chapter_opener" and page.page_break != "always":
            errors.append(f"Chapter opener {page.page_id} is not force page break")
        if page.page_class == "worksheet_page" and page.page_break == "auto":
            errors.append(f"Worksheet page {page.page_id} can split unexpectedly")
        if page.archetype == "table_page" and len(page.data.get("rows", [])) > 18:
            split_tables += 1
            warnings.append(f"Table may split across pages: {page.page_id}")
        if page.archetype == "chapter_body":
            for sec in page.data.get("sections", []):
                if sec.get("title") and not sec.get("content"):
                    orphan_headings += 1

    status = "pass" if not errors else "fail"
    return ValidationReport(
        build_status=status,
        errors=errors,
        warnings=warnings,
        stats={
            "page_count": len(composed.pages),
            "chapter_count": len(manual.chapters),
            "worksheet_count": len(manual.worksheets),
            "overflow_blocks": overflow_blocks,
            "split_tables": split_tables,
            "orphan_headings": orphan_headings,
        },
    )
