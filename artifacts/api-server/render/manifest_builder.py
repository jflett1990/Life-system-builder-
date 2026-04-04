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

import re as _re
from dataclasses import dataclass, field
from datetime import date
from typing import Any


# ── Narrative Formatter ─────────────────────────────────────────────────────────

def _format_narrative(text: str, max_chars: int = 2000) -> str:
    """Convert an AI-generated narrative string to readable HTML.

    Handles:
      - Markdown bold (**text** → <strong>text</strong>)
      - Inline numbered list items ("1. **Title**: desc") split to visual rows
      - Long single-paragraph text broken into readable ~60-word chunks
      - Truncation with a visual ellipsis

    Returns an HTML string safe for Jinja2 ``| safe`` rendering.
    """
    if not text:
        return ""

    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars].rstrip()

    # ── Step 1: Normalise line endings ──────────────────────────────────────
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # ── Step 2: Inject paragraph breaks before numbered list items ──────────
    # Pattern: "... sentence/colon end.  2. **Next**: ..." → "...\n\n2. **Next**: ..."
    # Also handles: "**Header**: 1. **Item**" → "**Header**:\n\n1. **Item**"
    text = _re.sub(r'(?<=[.!?:])\s+(\d+\.\s+\*\*)', r'\n\n\1', text)

    # ── Step 3: Split into paragraphs ───────────────────────────────────────
    raw_paragraphs = [p.strip() for p in _re.split(r'\n{2,}', text) if p.strip()]

    # If no double-newlines exist, split the single block at ~60-word boundaries
    if len(raw_paragraphs) == 1 and not _re.search(r'\d+\.\s+\*\*', text):
        sentences = _re.split(r'(?<=[.!?])\s+', raw_paragraphs[0])
        chunks, chunk, wc = [], [], 0
        for sent in sentences:
            chunk.append(sent)
            wc += len(sent.split())
            if wc >= 60:
                chunks.append(" ".join(chunk))
                chunk, wc = [], 0
        if chunk:
            chunks.append(" ".join(chunk))
        raw_paragraphs = chunks

    # ── Step 4: Render paragraphs ────────────────────────────────────────────
    html_parts: list[str] = []
    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check for numbered list item: "1. **Title**: description"
        m = _re.match(r'^(\d+)\.\s+\*\*(.+?)\*\*[:.]\s*(.*)', para, _re.DOTALL)
        if m:
            num = m.group(1)
            title = m.group(2)
            desc = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', m.group(3).strip())
            desc_html = (
                '<br><span style="font-size:0.9em;opacity:0.8">' + desc + '</span>'
                if desc else ""
            )
            html_parts.append(
                '<div style="display:flex;gap:0.6em;padding:0.35em 0;'
                'border-bottom:1px solid var(--color-rule);margin-bottom:0.25em;'
                'align-items:flex-start">'
                '<span style="color:var(--color-accent);flex-shrink:0;font-size:0.7em;'
                f'font-weight:700;margin-top:0.25em;min-width:1.2em">{num}</span>'
                '<div><strong style="font-size:0.72em;letter-spacing:0.06em;'
                f'text-transform:uppercase">{title}</strong>'
                f'{desc_html}'
                '</div></div>'
            )
        else:
            # Check for a standalone section header: "**Header**:" at start of para
            m2 = _re.match(r'^\*\*(.+?)\*\*:\s*(.*)', para, _re.DOTALL)
            if m2 and not m2.group(2).strip():
                # Pure header with no body text — render as subheading
                html_parts.append(
                    f'<p style="font-size:0.72em;font-weight:700;letter-spacing:0.06em;'
                    f'text-transform:uppercase;opacity:0.6;margin:1em 0 0.4em">'
                    f'{m2.group(1)}</p>'
                )
            else:
                para = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para)
                html_parts.append(
                    f'<p style="margin-bottom:0.75em;line-height:1.65">{para}</p>'
                )

    result = "".join(html_parts)
    if truncated:
        result += '<p style="opacity:0.5;font-size:0.85em;margin-top:0.5em">…</p>'
    return result


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

        # ── Pre-compute TOC data ────────────────────────────────────────────────
        toc_chapters = []
        if chapters:
            for ch in chapters:
                ch_ws = ch.get("worksheets", [])
                toc_chapters.append({
                    "chapter_number": ch.get("chapter_number", chapters.index(ch) + 1),
                    "chapter_title": ch.get("chapter_title", ""),
                    "worksheet_count": len(ch_ws),
                    "worksheets": [ws.get("title", "") for ws in ch_ws],
                })

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
                        "scope_items": ch_rules,
                        "primary_outputs": [ws.get("title", "") for ws in ch_worksheets],
                        "cascade_triggers": cascade_triggers,
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

                # One worksheet page per worksheet in this chapter
                for ws_idx, ws in enumerate(ch_worksheets):
                    ws_id = ws.get("id", f"ws-{ch_num}-{ws_idx + 1:02d}")
                    ws_data = dict(ws)
                    ws_data.setdefault("domain_name", domain_name)
                    # Pass chapter context so worksheet page can render running header
                    ws_data["chapter_number"] = ch_num
                    ws_data["chapter_title"] = ch_title
                    ws_data["system_name"] = system_name
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
                for ws in ch.get("worksheets", []):
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
            document_id=document_id,
            document_title=doc_title,
            system_name=system_name,
            theme_tokens=theme_tokens,
            pages=pages,
        )
