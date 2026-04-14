from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from render.composition_engine import compose_manual
from render.document_model import build_manual_document
from render.validation_report import validate_manual


@dataclass
class ManifestPage:
    page_id: str
    sequence: int
    archetype: str
    data: dict[str, Any]
    page_break: str = "always"


@dataclass
class RenderManifest:
    document_id: str
    document_title: str
    system_name: str
    theme_tokens: dict[str, str]
    pages: list[ManifestPage] = field(default_factory=list)
    validation_report: dict[str, Any] = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.pages)


class ManifestBuilder:
    """Build RenderManifest from a canonical manual model.

    Architecture:
      1) Content architecture layer: build_manual_document()
      2) Composition layer: compose_manual()
      3) Render validation layer: validate_manual()
    """

    def build(
        self,
        project_id: int,
        all_outputs: dict[str, Any],
        theme_tokens: dict[str, str],
    ) -> RenderManifest:
        # ── Phase 3 & 5: Content sanitation + quality gates ────────────────────
        # Runs first — removes LLM artifacts (duplicate headings, raw booleans,
        # placeholder text, JSON tokens) before any page data is assembled.
        from render.document_sanitizer import DocumentSanitizer, run_quality_gates
        from core.logging import get_logger as _get_logger
        _log = _get_logger(__name__)
        _sanitizer = DocumentSanitizer()
        _warnings = _sanitizer.sanitize(all_outputs)
        if _warnings:
            _log.info(
                "Document sanitizer: %d fixes applied (project %d)",
                len(_warnings), project_id,
            )
            for w in _warnings:
                if w.flagged:
                    _log.warning("Sanitizer flagged [%s] at %s: %r", w.issue, w.path, w.original)
        _gates = run_quality_gates(_warnings, all_outputs)
        if not _gates.passed:
            _log.warning("Quality gate failures (project %d): %s", project_id, _gates.failures)

        arch = all_outputs.get("system_architecture", {})
        chapter_exp = all_outputs.get("chapter_expansion", {})
        chapter_ws_stage = all_outputs.get("chapter_worksheets", {})
        ws_system   = all_outputs.get("worksheet_system", {})   # legacy fallback

        generated_date = date.today().strftime("%B %d, %Y")
        system_name = arch.get("system_name", "Operational Control System")
        doc_title = system_name
        document_id = f"LSB-{project_id:05d}"

        domains = arch.get("control_domains", [])
        domain_map: dict[str, dict] = {d.get("id", ""): d for d in domains}

        # Build worksheet lookup from the dedicated chapter_worksheets stage (new pipeline).
        # Falls back to worksheets embedded in chapter_expansion (old pipeline) for
        # backwards compatibility with existing projects.
        ws_by_chapter: dict[int, list[dict]] = {}
        if chapter_ws_stage:
            for ch_ws in chapter_ws_stage.get("chapters", []):
                ws_by_chapter[ch_ws.get("chapter_number", 0)] = ch_ws.get("worksheets") or []

        # Prefer chapter_expansion chapters; fall back to worksheet_system worksheets
        chapters: list[dict] = chapter_exp.get("chapters", [])
        legacy_worksheets: list[dict] = ws_system.get("worksheets", [])

        # Compute totals for KPIs — use chapter_worksheets counts when available
        if chapters:
            if ws_by_chapter:
                total_worksheets = sum(len(wsl) for wsl in ws_by_chapter.values() if wsl is not None)
            else:
                total_worksheets = sum(len(ch.get("worksheets", [])) for ch in chapters)
        else:
            total_worksheets = len(legacy_worksheets)

        pages: list[ManifestPage] = []
        seq = 0

        def next_seq() -> int:
            nonlocal seq
            seq += 1
            return seq

        # ── Pre-compute TOC data ────────────────────────────────────────────────
        toc_chapters = []
        if chapters:
            for ch in chapters:
                ch_num = ch.get("chapter_number", chapters.index(ch) + 1)
                ch_ws = ws_by_chapter.get(ch_num) if ws_by_chapter else ch.get("worksheets", [])
                if ch_ws is None:
                    ch_ws = []
                toc_chapters.append({
                    "chapter_number": ch_num,
                    "chapter_title": ch.get("chapter_title", ""),
                    "worksheet_count": len(ch_ws),
                    "worksheets": [ws.get("title", "") for ws in ch_ws],
                })

        # ── 1. Cover Page ──────────────────────────────────────────────────────
        pages.append(ManifestPage(
            page_id="pg-cover",
            sequence=next_seq(),
            archetype="cover_page",
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

        # ── 2. Table of Contents Page ──────────────────────────────────────────
        if toc_chapters:
            pages.append(ManifestPage(
                page_id="pg-toc",
                sequence=next_seq(),
                archetype="toc_page",
                data={
                    "chapters": toc_chapters,
                    "total_worksheets": total_worksheets,
                    "system_name": system_name,
                },
            ))

        # ── 3. Dashboard Page ──────────────────────────────────────────────────
        # Milestones come from system_architecture.critical_milestones, which
        # are the concrete project checkpoints (not chapter titles).
        # Falls back to success_criteria when no milestones were generated.
        success_criteria = arch.get("success_criteria", [])
        critical_milestones = arch.get("critical_milestones", [])

        if critical_milestones:
            milestones = critical_milestones[:8]
        elif success_criteria:
            milestones = [
                {"sequence": i, "milestone": criterion, "description": ""}
                for i, criterion in enumerate(success_criteria[:6], 1)
            ]
        else:
            milestones = []

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

        # ── 2b. Quick-start execution map (productization + stressed-user mode) ─
        if chapters:
            quick_start_steps = _collect_quick_start_steps(chapters)
            if quick_start_steps:
                pages.append(ManifestPage(
                    page_id="pg-quick-start",
                    sequence=next_seq(),
                    archetype="quick_start_page",
                    page_break="auto",
                    data={
                        "system_name": system_name,
                        "steps": quick_start_steps,
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
                page_break="auto",
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
            for ch_idx, ch in enumerate(chapters):
                ch_num = ch.get("chapter_number", ch_idx + 1)
                ch_title = ch.get("chapter_title", f"Chapter {ch_num}")
                ch_narrative = ch.get("narrative", "")
                ch_rules = ch.get("quick_reference_rules", [])
                # Prefer worksheets from the dedicated chapter_worksheets stage;
                # fall back to any worksheets embedded in chapter_expansion (old pipeline).
                ch_worksheets = (ws_by_chapter.get(ch_num) if ws_by_chapter else ch.get("worksheets", [])) or []

                # Resolve domain info from system_architecture
                domain_id = ch.get("domain_id", "")
                domain_info = domain_map.get(domain_id, {})
                domain_name = domain_info.get("name", "") or domain_id

                # Per-chapter section divider — gives every chapter its own dark intro page
                ch_num_str = f"{int(ch_num):02d}" if str(ch_num).isdigit() else str(ch_num)
                pages.append(ManifestPage(
                    page_id=f"pg-div-ch-{domain_id or ch_num}",
                    sequence=next_seq(),
                    archetype="section_divider",
                    data={
                        "label_prefix": "Chapter",
                        "section_number": ch_num_str,
                        "section_title": domain_name or ch_title,
                        "section_subtitle": ch_title if (domain_name and domain_name != ch_title) else "",
                        "domain_count": len(ch_worksheets),
                    },
                ))

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
                        "chapter_summary": _format_narrative(ch_narrative, max_chars=2000),
                        "domain_name": domain_name,
                        "domain_purpose": domain_info.get("purpose", ""),
                        "chapter_opener": ch.get("chapter_opener", {}),
                        "minimum_viable_actions": ch.get("minimum_viable_actions", []),
                        "scope_items": ch_rules,
                        "decision_guide": ch.get("decision_guide", []),
                        "trigger_blocks": ch.get("trigger_blocks", []),
                        "risk_blocks": ch.get("risk_blocks", []),
                        "output_summaries": ch.get("output_summaries", []),
                        "worksheet_linkage": ch.get("worksheet_linkage", []),
                        "detailed_explanation": _format_narrative(
                            ch.get("detailed_explanation", ch_narrative), max_chars=2800
                        ),
                        "primary_outputs": [ws.get("title", "") for ws in ch_worksheets],
                        "cascade_triggers": cascade_triggers,
                        "scenario_scene": ch.get("scenario_scene", ""),
                        "success_metrics": ch.get("success_metrics", []),
                    },
                ))

                # Quick Reference Card — inserted after chapter_opener
                pages.append(ManifestPage(
                    page_id=f"pg-refcard-{domain_id or ch_num}",
                    sequence=next_seq(),
                    archetype="reference_card_page",
                    data={
                        "chapter_number": ch_num,
                        "chapter_title": ch_title,
                        "domain_name": domain_name,
                        "quick_reference_rules": ch_rules,
                        "cascade_triggers": cascade_triggers,
                        "primary_outputs": [ws.get("title", "") for ws in ch_worksheets],
                    },
                ))

                # Domain color for this chapter — cycles through palette by chapter index
                ch_color = DOMAIN_COLORS[ch_idx % len(DOMAIN_COLORS)]

                # One worksheet page per worksheet in this chapter
                for ws_idx, ws in enumerate(ch_worksheets):
                    ws_id = ws.get("id", f"ws-{ch_num}-{ws_idx + 1:02d}")
                    ws_data = dict(ws)
                    ws_data.setdefault("domain_name", domain_name)
                    # Pass chapter context so worksheet page can render running header
                    ws_data["chapter_number"] = ch_num
                    ws_data["chapter_title"] = ch_title
                    ws_data["system_name"] = system_name
                    # Domain colour injected as CSS custom-property values (Task 3)
                    ws_data["domain_color"] = ch_color["primary"]
                    ws_data["domain_color_light"] = ch_color["light"]
                    pages.append(ManifestPage(
                        page_id=f"pg-ws-{ws_id}",
                        sequence=next_seq(),
                        archetype="worksheet_page",
                        # First worksheet in a chapter always starts a fresh page;
                        # subsequent worksheets flow continuously so Pagedjs can pack
                        # content without wasting nearly-empty pages.
                        page_break="always" if ws_idx == 0 else "auto",
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
                        "chapter_summary": _format_narrative(ws.get("purpose", "")),
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

        # ── 7. Worksheet Index Page ────────────────────────────────────────────
        # Alphabetically sorted index of all worksheets (chapter_expansion path only)
        if chapters:
            all_ws_entries = []
            for ch in chapters:
                ch_num = ch.get("chapter_number", chapters.index(ch) + 1)
                ch_title = ch.get("chapter_title", f"Chapter {ch_num}")
                ch_ws_list = (ws_by_chapter.get(ch_num) if ws_by_chapter else ch.get("worksheets", [])) or []
                for ws in ch_ws_list:
                    ws_title = ws.get("title", "")
                    if ws_title:
                        all_ws_entries.append({
                            "title": ws_title,
                            "chapter_number": ch_num,
                            "chapter_title": ch_title,
                        })
            if all_ws_entries:
                all_ws_entries.sort(key=lambda e: e["title"].lower())
                pages.append(ManifestPage(
                    page_id="pg-ws-index",
                    sequence=next_seq(),
                    archetype="worksheet_index_page",
                    page_break="auto",
                    data={
                        "index_entries": all_ws_entries,
                        "total_worksheets": len(all_ws_entries),
                        "total_chapters": len(chapters),
                    },
                ))

        # ── 8. Appendix Pages (when appendix_builder output is present) ────────
        appendix = all_outputs.get("appendix_builder", {})
        if appendix:
            glossary_terms = appendix.get("glossary_terms", [])
            professional_triggers = appendix.get("professional_triggers", [])
            key_resources = appendix.get("key_resources", [])
            include_notes = appendix.get("include_notes_pages", True)
            notes_count = appendix.get("notes_page_count", 3)
            life_event = appendix.get("life_event", arch.get("life_event", ""))

            # Appendix section divider
            pages.append(ManifestPage(
                page_id="pg-div-appendix",
                sequence=next_seq(),
                archetype="section_divider",
                data={
                    "section_number": "A",
                    "section_title": "Appendix",
                    "section_subtitle": "Reference materials, glossary, and professional guidance",
                    "domain_count": None,
                },
            ))

            # Appendix A: Glossary
            if glossary_terms:
                pages.append(ManifestPage(
                    page_id="pg-appendix-glossary",
                    sequence=next_seq(),
                    archetype="appendix_glossary",
                    page_break="auto",
                    data={
                        "life_event": life_event,
                        "glossary_terms": glossary_terms,
                    },
                ))

            # Appendix B: When to Call a Professional
            if professional_triggers:
                pages.append(ManifestPage(
                    page_id="pg-appendix-professional-guide",
                    sequence=next_seq(),
                    archetype="appendix_professional_guide",
                    page_break="auto",
                    data={
                        "life_event": life_event,
                        "professional_triggers": professional_triggers,
                    },
                ))

            # Appendix C: Key Resources & Contacts (table worksheet)
            if key_resources:
                pages.append(ManifestPage(
                    page_id="pg-appendix-key-resources",
                    sequence=next_seq(),
                    archetype="worksheet_page",
                    page_break="auto",
                    data={
                        "id": "appendix-key-resources",
                        "title": "Key Resources & Contacts",
                        "purpose": "Use this worksheet to record the organizations, agencies, and professionals relevant to your situation. Fill in contact details as you gather them.",
                        "layout": "table",
                        "table_columns": ["Organization", "Service", "Phone", "Website", "Hours"],
                        "table_row_count": max(len(key_resources), 10),
                        "system_name": system_name,
                        "domain_name": "Reference",
                        "chapter_number": None,
                        "chapter_title": "Appendix C",
                        "_key_resources_prefill": key_resources,
                    },
                ))

            # Appendix D–F: Notes pages
            if include_notes:
                for note_page_idx in range(max(notes_count, 1)):
                    pages.append(ManifestPage(
                        page_id=f"pg-appendix-notes-{note_page_idx + 1}",
                        sequence=next_seq(),
                        archetype="appendix_notes",
                        page_break="auto",
                        data={
                            "page_number": note_page_idx + 1,
                            "total_pages": notes_count,
                        },
                    ))

        # ── 9. Rapid Response Page ─────────────────────────────────────────────
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
            document_id=manual.id,
            document_title=manual.title,
            system_name=manual.title,
            theme_tokens=theme_tokens,
            pages=pages,
            validation_report=report.to_dict(),
        )
