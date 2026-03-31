"""
ManifestBuilder — maps validated pipeline stage outputs into an ordered list
of ManifestPage objects.  Each page declares its archetype, page ID, sequence
number, and the data payload the archetype template needs.

The manifest is the contract between the pipeline and the renderer.  The renderer
does no content decisions — it only iterates pages and includes the right template.

Stage data sources (in priority order):
  chapter_expansion   — rich per-chapter narratives + worksheets (current pipeline)
  worksheet_system    — legacy flat worksheet list (pre-chapter_expansion projects)
  system_architecture — architecture, domains, roles, constraints, failure modes
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


# ── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class ManifestPage:
    page_id: str
    sequence: int
    archetype: str          # must match a templates/pages/<archetype>.html file
    data: dict[str, Any]
    page_break_before: bool = True


@dataclass
class RenderManifest:
    document_id: str
    document_title: str
    system_name: str
    theme_tokens: dict[str, str]
    pages: list[ManifestPage] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)


# ── Builder ────────────────────────────────────────────────────────────────────

class ManifestBuilder:
    """
    Consumes the dict of {stage_name: stage_output} returned by
    PipelineService.all_stage_outputs_as_dict() and produces a RenderManifest.

    Page sequence:
      1  cover_page           — system identity
      2  dashboard_page        — system objective callout, KPIs, chapter milestones, success criteria
      3  section_divider       — "System Architecture" divider
      4  explanation_page      — operating premise, domains, constraints
      [for each chapter in chapter_expansion]:
        N  section_divider     — "Operational Content" divider (once, before first chapter)
        N  chapter_opener      — domain intro, narrative, quick-reference rules, cascade triggers
        N  worksheet_page(s)   — one page per worksheet in this chapter
      [legacy: worksheet_system path if chapter_expansion absent]
      -1  rapid_response       — failure modes + escalation paths
    """

    def build(
        self,
        project_id: int,
        all_outputs: dict[str, Any],
        theme_tokens: dict[str, str],
    ) -> RenderManifest:
        arch = all_outputs.get("system_architecture", {})
        chapter_exp = all_outputs.get("chapter_expansion", {})
        ws_system   = all_outputs.get("worksheet_system", {})   # legacy fallback

        generated_date = date.today().strftime("%B %d, %Y")
        system_name = arch.get("system_name", "Operational Control System")
        doc_title = system_name
        document_id = f"LSB-{project_id:05d}"

        domains = arch.get("control_domains", [])
        domain_map: dict[str, dict] = {d.get("id", ""): d for d in domains}

        # Prefer chapter_expansion chapters; fall back to worksheet_system worksheets
        chapters: list[dict] = chapter_exp.get("chapters", [])
        legacy_worksheets: list[dict] = ws_system.get("worksheets", [])

        # Compute totals for KPIs
        if chapters:
            total_worksheets = sum(len(ch.get("worksheets", [])) for ch in chapters)
        else:
            total_worksheets = len(legacy_worksheets)

        pages: list[ManifestPage] = []
        seq = 0

        def next_seq() -> int:
            nonlocal seq
            seq += 1
            return seq

        # ── 1. Cover Page ──────────────────────────────────────────────────────
        pages.append(ManifestPage(
            page_id="pg-cover",
            sequence=next_seq(),
            archetype="cover_page",
            page_break_before=False,
            data={
                "system_name": system_name,
                "life_event": arch.get("life_event", ""),
                "system_objective": arch.get("system_objective", ""),
                "time_horizon": arch.get("time_horizon", ""),
                "audience": arch.get("audience", ""),
                "generated_date": generated_date,
                "document_id": document_id,
            },
        ))

        # ── 2. Dashboard Page ──────────────────────────────────────────────────
        # Milestones = chapter titles (differentiated, content-specific).
        # Falls back to success_criteria only when no chapters exist.
        success_criteria = arch.get("success_criteria", [])

        if chapters:
            milestones = [
                {
                    "sequence": i,
                    "milestone": ch.get("chapter_title", f"Chapter {i}"),
                    "description": "",
                }
                for i, ch in enumerate(chapters[:8], 1)
            ]
        else:
            milestones = [
                {"sequence": i, "milestone": criterion, "description": ""}
                for i, criterion in enumerate(success_criteria[:6], 1)
            ]

        kpis: list[dict] = []
        if total_worksheets:
            kpis.append({"value": str(total_worksheets), "label": "Worksheets"})

        pages.append(ManifestPage(
            page_id="pg-dashboard",
            sequence=next_seq(),
            archetype="dashboard_page",
            data={
                "page_label": "System Overview",
                "page_title": "Operational Dashboard",
                "system_name": system_name,
                "system_objective": arch.get("system_objective", ""),
                "time_horizon": arch.get("time_horizon", ""),
                "domain_count": len(domains) if domains else None,
                "worksheet_count": None,        # shown via KPI block instead
                "success_criteria": success_criteria,
                "milestones": milestones,
                "generated_date": generated_date,
                "kpis": kpis,
            },
        ))

        # ── 3. Architecture Section Divider ────────────────────────────────────
        pages.append(ManifestPage(
            page_id="pg-div-arch",
            sequence=next_seq(),
            archetype="section_divider",
            data={
                "section_number": "01",
                "section_title": "System Architecture",
                "section_subtitle": arch.get("operating_premise", "")[:140] if arch.get("operating_premise") else "",
                "domain_count": len(domains),
            },
        ))

        # ── 4. Explanation Page ────────────────────────────────────────────────
        # Intentionally omits key_roles (repetitive — not project-differentiated)
        # and success_criteria (shown on dashboard) to avoid duplication.
        if arch:
            pages.append(ManifestPage(
                page_id="pg-arch-explain",
                sequence=next_seq(),
                archetype="explanation_page",
                data={
                    "page_label": "System Architecture",
                    "page_title": system_name,
                    "operating_premise": arch.get("operating_premise", ""),
                    "system_objective": arch.get("system_objective", ""),
                    "key_roles": [],                       # suppressed — avoid generic role section
                    "control_domains": domains,
                    "success_criteria": [],                # suppressed — on dashboard
                    "failure_modes": arch.get("failure_modes", []),
                    "operating_constraints": arch.get("operating_constraints", []),
                    "time_horizon": arch.get("time_horizon", ""),
                },
            ))

        # ── 6a. Chapters from chapter_expansion (current pipeline) ─────────────
        if chapters:
            total_chapters = len(chapters)
            pages.append(ManifestPage(
                page_id="pg-div-chapters",
                sequence=next_seq(),
                archetype="section_divider",
                data={
                    "section_number": "02",
                    "section_title": "Operational Content",
                    "section_subtitle": f"{total_chapters} chapters · {total_worksheets} worksheets",
                    "domain_count": total_chapters,
                },
            ))

            for ch in chapters:
                ch_num = ch.get("chapter_number", chapters.index(ch) + 1)
                ch_title = ch.get("chapter_title", f"Chapter {ch_num}")
                ch_narrative = ch.get("narrative", "")
                ch_rules = ch.get("quick_reference_rules", [])
                ch_worksheets = ch.get("worksheets", [])

                # Resolve domain info from system_architecture
                domain_id = ch.get("domain_id", "")
                domain_info = domain_map.get(domain_id, {})
                domain_name = domain_info.get("name", "") or domain_id

                # chapter_opener: show chapter intro + quick-reference rules as scope items
                # primary_outputs: worksheet titles in this chapter
                # cascade_triggers: downstream dependencies that activate if this chapter fails
                cascade_triggers = ch.get("cascade_triggers", [])
                pages.append(ManifestPage(
                    page_id=f"pg-chapter-{domain_id or ch_num}",
                    sequence=next_seq(),
                    archetype="chapter_opener",
                    data={
                        "chapter_number": ch_num,
                        "chapter_title": ch_title,
                        "chapter_summary": ch_narrative[:2000].rstrip() + ("…" if len(ch_narrative) > 2000 else ""),
                        "domain_name": domain_name,
                        "domain_purpose": domain_info.get("purpose", ""),
                        "scope_items": ch_rules,
                        "primary_outputs": [ws.get("title", "") for ws in ch_worksheets],
                        "cascade_triggers": cascade_triggers,
                    },
                ))

                # One worksheet page per worksheet in this chapter
                for ws in ch_worksheets:
                    ws_id = ws.get("id", f"ws-{ch_num}-{ch_worksheets.index(ws) + 1:02d}")
                    ws_data = dict(ws)
                    ws_data.setdefault("domain_name", domain_name)
                    pages.append(ManifestPage(
                        page_id=f"pg-ws-{ws_id}",
                        sequence=next_seq(),
                        archetype="worksheet_page",
                        data=ws_data,
                    ))

        # ── 6b. Legacy path: worksheet_system (pre-chapter_expansion projects) ─
        elif legacy_worksheets:
            pages.append(ManifestPage(
                page_id="pg-div-ws",
                sequence=next_seq(),
                archetype="section_divider",
                data={
                    "section_number": "02",
                    "section_title": "Operational Worksheets",
                    "section_subtitle": ws_system.get("worksheet_system_name", ""),
                    "domain_count": len(legacy_worksheets),
                },
            ))

            for i, ws in enumerate(legacy_worksheets):
                ws_id = ws.get("id", f"ws-{i+1:02d}")
                domain_id = ws.get("domain_id", "")
                domain_name = ws.get("domain_name", "")
                matching_domain = domain_map.get(domain_id, {})

                pages.append(ManifestPage(
                    page_id=f"pg-chapter-{ws_id}",
                    sequence=next_seq(),
                    archetype="chapter_opener",
                    data={
                        "chapter_number": i + 1,
                        "chapter_title": ws.get("title", f"Worksheet {i+1}"),
                        "chapter_summary": ws.get("purpose", ""),
                        "domain_name": domain_name,
                        "domain_purpose": matching_domain.get("purpose", ""),
                        "scope_items": matching_domain.get("scope_in", []),
                        "primary_outputs": matching_domain.get("primary_outputs", []),
                    },
                ))
                pages.append(ManifestPage(
                    page_id=f"pg-ws-{ws_id}",
                    sequence=next_seq(),
                    archetype="worksheet_page",
                    data=ws,
                ))

        # ── 7. Rapid Response Page ─────────────────────────────────────────────
        failure_modes = arch.get("failure_modes", [])
        if failure_modes or arch.get("operating_constraints"):
            structured_modes = []
            for mode in failure_modes:
                if isinstance(mode, str):
                    structured_modes.append({"trigger": mode, "description": "", "response": ""})
                elif isinstance(mode, dict):
                    structured_modes.append(mode)

            pages.append(ManifestPage(
                page_id="pg-rapid-response",
                sequence=next_seq(),
                archetype="rapid_response",
                data={
                    "page_label": "Contingency Protocol",
                    "page_title": "Rapid Response Reference",
                    "failure_modes": structured_modes,
                    "operating_constraints": arch.get("operating_constraints", []),
                    "escalation_paths": arch.get("escalation_paths", []),
                    "checklists": [],
                },
            ))

        return RenderManifest(
            document_id=document_id,
            document_title=doc_title,
            system_name=system_name,
            theme_tokens=theme_tokens,
            pages=pages,
        )
