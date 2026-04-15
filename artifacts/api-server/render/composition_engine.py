from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from render.document_model import ManualDocument, ManualChapter, ManualWorksheet


@dataclass
class ComposedBlock:
    component: str
    data: dict[str, Any]
    keep_with_next: bool = False
    keep_together: bool = False


@dataclass
class ComposedPage:
    page_id: str
    page_class: str
    archetype: str
    page_break: str
    blocks: list[ComposedBlock] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComposedDocument:
    document_id: str
    title: str
    pages: list[ComposedPage]


def compose_manual(manual: ManualDocument) -> ComposedDocument:
    pages: list[ComposedPage] = []

    def add_page(page_class: str, archetype: str, data: dict[str, Any], page_break: str = "always", blocks: list[ComposedBlock] | None = None) -> None:
        pages.append(
            ComposedPage(
                page_id=f"pg-{len(pages)+1:03d}-{page_class.replace('_', '-')}",
                page_class=page_class,
                archetype=archetype,
                page_break=page_break,
                blocks=blocks or [],
                data=data,
            )
        )

    add_page("cover", "cover_page", {"system_name": manual.title, "system_objective": manual.objective, "audience": manual.audience, "time_horizon": manual.time_horizon, "document_id": manual.id})
    add_page("disclaimer", "disclaimer_page", {"title": "Professional Use Notice", "body": "This manual is an operational planning aid. It does not replace legal, financial, legal, tax, or medical advice. Validate decisions with licensed professionals when required."})
    add_page("about", "about_page", {"title": "About This Manual", "body": manual.subtitle or "Use this manual to run work consistently under normal and high-pressure conditions."}, page_break="auto")
    add_page("contents", "toc_page", {
        "chapters": [{"chapter_number": i + 1, "chapter_title": ch.title, "worksheet_count": len(ch.worksheet_refs), "worksheets": []} for i, ch in enumerate(manual.chapters)],
        "total_worksheets": len(manual.worksheets),
        "system_name": manual.title,
    })

    add_page("system_overview_opener", "editorial_page", {"label": "System Overview", "title": "Operating model", "body": manual.objective}, page_break="auto")
    add_page("operating_model", "table_page", {"title": "Operational Domains", "columns": ["Domain", "Purpose", "Chapter Refs"], "rows": [[d.title, d.purpose, ", ".join(d.chapter_refs)] for d in manual.domains]}, page_break="auto")
    add_page("master_operating_rules", "table_page", {"title": "Master Operating Rules", "columns": ["Rule", "Intent"], "rows": [["Keep records current", "Avoid stale assumptions and stale dependencies"], ["Escalate before failure", "Prevent cascading loss and reactive rework"], ["Log every decision", "Preserve context across tools and sessions"]]}, page_break="auto")
    add_page("cascade_chain", "table_page", {"title": "Cascade Chain / Dependency Logic", "columns": ["Upstream", "Dependency", "Downstream"], "rows": [["Inputs", "Decision quality", "Execution"], ["Execution", "Review cadence", "Corrective action"], ["Documentation", "Recoverability", "Operational continuity"]]}, page_break="auto")
    add_page("how_to_use", "editorial_page", {"label": "Orientation", "title": "How to Use / Navigate", "body": "Read front matter once, then run one chapter at a time, finish the checklist, and complete worksheets in chapter order before advancing."}, page_break="auto")
    add_page("command_center", "editorial_page", {"label": "Operations", "title": "Command Center / Operating Base", "body": "Keep one source of truth for specs, tasks, runbooks, credentials references, and review cadence so work can continue from desktop or mobile."}, page_break="auto")
    add_page("where_to_start", "editorial_page", {"label": "Start", "title": "Where to Start", "body": "Start with the chapter carrying the earliest risk horizon; complete worksheets tagged COMPLETE EARLY first."}, page_break="auto")
    add_page("core_failure_modes", "table_page", {"title": "Core Failure Modes", "columns": ["Failure", "Mitigation"], "rows": [["No owner assigned", "Assign explicit ownership"], ["Out-of-date assumptions", "Run monthly review"], ["Undocumented handoffs", "Capture decisions in repo artifacts"]]}, page_break="auto")
    add_page("review_cadence", "table_page", {"title": "Review Cadence", "columns": ["Cadence", "What to review"], "rows": [["Weekly", "active tasks and blockers"], ["Monthly", "status snapshots and trackers"], ["Quarterly", "decision framework and dependencies"]]}, page_break="auto")
    add_page("decision_framework", "table_page", {"title": "Decision Framework", "columns": ["Question", "Threshold", "Action"], "rows": [["Is risk increasing?", "Yes", "Escalate and revise"], ["Is ownership clear?", "No", "Assign before continuing"], ["Is context captured?", "No", "Update specs/tasks before merge"]]}, page_break="auto")
    add_page("emergency_navigation", "quick_index_page", {"title": "Emergency Navigation", "entries": [{"label": ch.title, "ref": ch.id} for ch in manual.chapters]}, page_break="auto")

    for idx, chapter in enumerate(manual.chapters, start=1):
        _add_chapter_pages(add_page, idx, chapter, manual)

    if manual.appendices:
        for appendix in manual.appendices:
            add_page("appendix", "quick_index_page", {"title": appendix.get("title", "Appendix"), "entries": appendix.get("entries", [])})

    return ComposedDocument(document_id=manual.id, title=manual.title, pages=pages)


def _add_chapter_pages(add_page, idx: int, chapter: ManualChapter, manual: ManualDocument) -> None:
    add_page("chapter_opener", "chapter_opener", {
        "chapter_number": idx,
        "chapter_title": chapter.title,
        "chapter_summary": chapter.purpose,
        "domain_name": ", ".join(chapter.domain_refs),
        "scope_items": chapter.checklists[:5],
        "primary_outputs": chapter.worksheet_refs,
    }, page_break="always")

    add_page(
        "chapter_body",
        "chapter_body",
        {
            "chapter_number": idx,
            "chapter_title": chapter.title,
            "sections": [{"title": sec.title, "type": sec.type, "content": sec.content} for sec in chapter.sections],
        },
        page_break="auto",
    )

    for ws_idx, ws_id in enumerate(chapter.worksheet_refs, start=1):
        ws = next((w for w in manual.worksheets if w.id == ws_id), None)
        if not ws:
            continue
        _add_worksheet_page(add_page, idx, ws_idx, chapter, ws, manual.title)


def _add_worksheet_page(add_page, chapter_num: int, worksheet_num: int, chapter: ManualChapter, ws: ManualWorksheet, system_name: str) -> None:
    add_page(
        "worksheet_page",
        "worksheet_page",
        {
            "id": ws.id,
            "title": ws.title,
            "purpose": ws.instruction,
            "usage_tag": ws.usage_tag,
            "layout": "table" if ws.layout_type == "log" else ws.layout_type,
            "sections": ws.fields,
            "chapter_number": chapter_num,
            "chapter_title": chapter.title,
            "worksheet_number": worksheet_num,
            "system_name": system_name,
            "instruction": ws.instruction,
        },
        page_break="always",
    )
