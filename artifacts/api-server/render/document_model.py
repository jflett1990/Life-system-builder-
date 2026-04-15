from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SectionType = Literal[
    "body",
    "table",
    "scenario_box",
    "warning_box",
    "key_insight",
    "checklist",
    "decision_framework",
    "review_calendar",
    "cascade_map",
]

PageBreakPolicy = Literal[
    "auto",
    "keep_with_next",
    "keep_together",
    "force_page_break_before",
]


@dataclass
class ManualSection:
    id: str
    type: SectionType
    title: str
    content: dict[str, Any]
    page_break_policy: PageBreakPolicy = "auto"


@dataclass
class ManualWorksheet:
    id: str
    chapter_ref: str
    usage_tag: str
    title: str
    instruction: str
    layout_type: Literal["table", "form", "matrix", "log", "checklist"]
    fields: list[dict[str, Any]] = field(default_factory=list)
    page_break_policy: PageBreakPolicy = "keep_together"


@dataclass
class ManualChapter:
    id: str
    title: str
    subtitle: str
    domain_refs: list[str]
    purpose: str
    sections: list[ManualSection] = field(default_factory=list)
    checklists: list[str] = field(default_factory=list)
    worksheet_refs: list[str] = field(default_factory=list)


@dataclass
class ManualDomain:
    id: str
    title: str
    purpose: str
    chapter_refs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


@dataclass
class ManualDocument:
    id: str
    title: str
    subtitle: str
    audience: str
    objective: str
    time_horizon: str
    front_matter: list[dict[str, Any]]
    domains: list[ManualDomain]
    chapters: list[ManualChapter]
    worksheets: list[ManualWorksheet]
    appendices: list[dict[str, Any]]


USAGE_TAGS = {
    "COMPLETE EARLY",
    "COMPLETE BEFORE CRISIS",
    "REVIEW MONTHLY",
    "REVIEW QUARTERLY",
    "UPDATE AFTER EACH EVALUATION",
    "USE DURING TRANSITIONS",
}

FRONT_MATTER_SEQUENCE = [
    "cover",
    "disclaimer",
    "about",
    "contents",
    "system_overview_opener",
    "operational_domains",
    "master_operating_rules",
    "cascade_chain",
    "how_to_use",
    "command_center",
    "where_to_start",
    "core_failure_modes",
    "review_cadence",
    "decision_framework",
    "emergency_navigation",
]


def build_manual_document(project_id: int, all_outputs: dict[str, Any]) -> ManualDocument:
    arch = all_outputs.get("system_architecture", {})
    chapter_exp = all_outputs.get("chapter_expansion", {})
    chapter_ws = all_outputs.get("chapter_worksheets", {})
    outline = all_outputs.get("document_outline", {})

    document_id = f"LSB-{project_id:05d}"
    title = arch.get("system_name") or outline.get("document_title") or "Operational Reference Manual"
    subtitle = outline.get("subtitle") or "Operating system and worksheets"

    domains_raw = arch.get("control_domains", [])
    domains: list[ManualDomain] = []
    for idx, d in enumerate(domains_raw):
        did = d.get("id") or f"dom-{idx+1:02d}"
        domains.append(
            ManualDomain(
                id=did,
                title=d.get("name") or d.get("title") or f"Domain {idx+1}",
                purpose=d.get("purpose", ""),
                chapter_refs=[],
                outputs=d.get("primary_outputs", []) if isinstance(d.get("primary_outputs", []), list) else [],
            )
        )

    ws_by_chapter: dict[int, list[dict[str, Any]]] = {}
    for ch in chapter_ws.get("chapters", []):
        ws_by_chapter[ch.get("chapter_number", 0)] = ch.get("worksheets", [])

    chapters: list[ManualChapter] = []
    worksheets: list[ManualWorksheet] = []

    for idx, ch in enumerate(chapter_exp.get("chapters", [])):
        ch_num = int(ch.get("chapter_number", idx + 1))
        ch_id = f"ch-{ch_num:02d}"
        domain_id = ch.get("domain_id")
        if not domain_id and domains:
            domain_id = domains[min(idx, len(domains) - 1)].id

        quick_rules = ch.get("quick_reference_rules", [])
        decision_rows = ch.get("decision_guide", [])
        scenario_scene = ch.get("scenario_scene", "")
        cascade_rows = ch.get("cascade_triggers", [])
        detailed = ch.get("detailed_explanation") or ch.get("narrative", "")

        sections = [
            ManualSection(
                id=f"sec-{ch_num:02d}-a",
                type="body",
                title="Why this topic matters",
                content={"text": ch.get("chapter_opener", {}).get("when_it_matters") or ch.get("narrative", "")},
                page_break_policy="keep_with_next",
            ),
            ManualSection(
                id=f"sec-{ch_num:02d}-b",
                type="key_insight",
                title="Key concepts and failure patterns",
                content={
                    "text": detailed,
                    "items": ch.get("risk_blocks", []),
                    "rules": quick_rules,
                },
                page_break_policy="keep_together",
            ),
            ManualSection(
                id=f"sec-{ch_num:02d}-c",
                type="decision_framework",
                title="Decision logic",
                content={"rows": decision_rows},
                page_break_policy="auto",
            ),
            ManualSection(
                id=f"sec-{ch_num:02d}-d",
                type="scenario_box",
                title="Scenario",
                content={"text": scenario_scene},
                page_break_policy="keep_together",
            ),
            ManualSection(
                id=f"sec-{ch_num:02d}-e",
                type="cascade_map",
                title="Cascade / dependency map",
                content={"rows": cascade_rows},
                page_break_policy="auto",
            ),
            ManualSection(
                id=f"sec-{ch_num:02d}-f",
                type="checklist",
                title="Operational checklist",
                content={"items": ch.get("minimum_viable_actions", [])},
                page_break_policy="keep_together",
            ),
        ]

        chapter = ManualChapter(
            id=ch_id,
            title=ch.get("chapter_title") or f"Chapter {ch_num}",
            subtitle=(ch.get("chapter_opener", {}) or {}).get("framing_line", ""),
            domain_refs=[domain_id] if domain_id else [],
            purpose=ch.get("chapter_opener", {}).get("promise", ""),
            sections=sections,
            checklists=ch.get("minimum_viable_actions", []),
            worksheet_refs=[],
        )
        chapters.append(chapter)

        chapter_ws_items = ws_by_chapter.get(ch_num) or ch.get("worksheets", [])
        for w_idx, ws in enumerate(chapter_ws_items):
            usage_tag = str(ws.get("usage_tag") or "COMPLETE EARLY").upper()
            if usage_tag not in USAGE_TAGS:
                usage_tag = "COMPLETE EARLY"
            ws_id = ws.get("id") or f"ws-{ch_num:02d}-{w_idx+1:02d}"
            layout = ws.get("layout") or ws.get("layout_type") or "form"
            normalized_layout = layout if layout in {"table", "form", "matrix", "log", "checklist"} else "form"
            worksheet = ManualWorksheet(
                id=ws_id,
                chapter_ref=ch_id,
                usage_tag=usage_tag,
                title=ws.get("title") or f"Worksheet {w_idx+1}",
                instruction=ws.get("instruction") or ws.get("purpose") or "Complete this worksheet to capture operational inputs.",
                layout_type=normalized_layout,
                fields=ws.get("sections", []) if isinstance(ws.get("sections", []), list) else [],
            )
            worksheets.append(worksheet)
            chapter.worksheet_refs.append(ws_id)

    for d in domains:
        d.chapter_refs = [c.id for c in chapters if d.id in c.domain_refs]

    front_matter = [{"id": key, "title": key.replace("_", " ").title()} for key in FRONT_MATTER_SEQUENCE]

    appendices: list[dict[str, Any]] = []
    appendix = all_outputs.get("appendix_builder", {})
    if appendix:
        appendices.append({
            "id": "app-quick-index",
            "title": "Quick Index",
            "entries": appendix.get("key_resources", []),
        })

    return ManualDocument(
        id=document_id,
        title=title,
        subtitle=subtitle,
        audience=arch.get("audience", "general audience"),
        objective=arch.get("system_objective", ""),
        time_horizon=arch.get("time_horizon", ""),
        front_matter=front_matter,
        domains=domains,
        chapters=chapters,
        worksheets=worksheets,
        appendices=appendices,
    )
