"""
ManifestBuilder — maps validated pipeline stage outputs into an ordered list
of ManifestPage objects.  Each page declares its archetype, page ID, sequence
number, and the data payload the archetype template needs.

The manifest is the contract between the pipeline and the renderer.  The renderer
does no content decisions — it only iterates pages and includes the right template.
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
      1  cover_page          — system identity
      2  dashboard_page       — KPIs, milestones, success criteria
      3  section_divider      — "System Architecture" divider
      4  explanation_page     — operating premise, roles, domains, constraints
      5  comparison_matrix    — role × domain responsibility grid
      [for each worksheet]:
        N  section_divider    — domain divider
        N  chapter_opener     — domain chapter
        N  worksheet_page     — the worksheet itself
      -2  rapid_response      — failure modes + escalation paths
    """

    def build(
        self,
        project_id: int,
        all_outputs: dict[str, Any],
        theme_tokens: dict[str, str],
    ) -> RenderManifest:
        arch = all_outputs.get("system_architecture", {})
        ws_system = all_outputs.get("worksheet_system", {})
        generated_date = date.today().strftime("%B %d, %Y")
        system_name = arch.get("system_name", "Operational Control System")
        doc_title = system_name
        document_id = f"LSB-{project_id:05d}"

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
        domains = arch.get("control_domains", [])
        worksheets = ws_system.get("worksheets", [])
        success_criteria = arch.get("success_criteria", [])

        milestones = []
        for i, criterion in enumerate(success_criteria[:6], 1):
            milestones.append({"sequence": i, "milestone": criterion, "description": ""})

        pages.append(ManifestPage(
            page_id="pg-dashboard",
            sequence=next_seq(),
            archetype="dashboard_page",
            data={
                "page_label": "System Overview",
                "page_title": "Operational Dashboard",
                "system_name": system_name,
                "time_horizon": arch.get("time_horizon", ""),
                "domain_count": len(domains) if domains else None,
                "worksheet_count": len(worksheets) if worksheets else None,
                "success_criteria": success_criteria,
                "milestones": milestones,
                "generated_date": generated_date,
                "kpis": [],
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
                    "key_roles": arch.get("key_roles", []),
                    "control_domains": domains,
                    "success_criteria": arch.get("success_criteria", []),
                    "failure_modes": arch.get("failure_modes", []),
                    "operating_constraints": arch.get("operating_constraints", []),
                    "time_horizon": arch.get("time_horizon", ""),
                },
            ))

        # ── 5. Role × Domain Comparison Matrix ────────────────────────────────
        roles = arch.get("key_roles", [])
        if roles and domains:
            columns = [d.get("name", d.get("id", "Domain")) for d in domains]
            rows = []
            for role in roles:
                cells: dict[str, str] = {}
                for domain in domains:
                    col_name = domain.get("name", domain.get("id", ""))
                    cells[col_name] = role.get("authority_level", "executor").replace("-", " ").title()
                rows.append({
                    "label": role.get("role", ""),
                    "sublabel": role.get("authority_level", ""),
                    "cells": cells,
                })
            pages.append(ManifestPage(
                page_id="pg-matrix-roles",
                sequence=next_seq(),
                archetype="comparison_matrix",
                data={
                    "matrix_label": "Responsibility Matrix",
                    "matrix_title": "Roles × Control Domains",
                    "subtitle": "Authority and engagement level per domain.",
                    "row_header": "Role",
                    "columns": columns,
                    "rows": rows,
                    "notes": "Authority levels reflect decision-making power within each control domain.",
                },
            ))

        # ── 6. Worksheets Section ──────────────────────────────────────────────
        if worksheets:
            pages.append(ManifestPage(
                page_id="pg-div-ws",
                sequence=next_seq(),
                archetype="section_divider",
                data={
                    "section_number": "02",
                    "section_title": "Operational Worksheets",
                    "section_subtitle": ws_system.get("worksheet_system_name", ""),
                    "domain_count": len(worksheets),
                },
            ))

            for i, ws in enumerate(worksheets):
                ws_id = ws.get("id", f"ws-{i+1:02d}")
                domain_id = ws.get("domain_id", "")
                domain_name = ws.get("domain_name", "")

                # Find matching domain for chapter context
                matching_domain = next(
                    (d for d in domains if d.get("id") == domain_id),
                    {}
                )

                # Chapter opener for each worksheet
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

                # Worksheet page
                pages.append(ManifestPage(
                    page_id=f"pg-ws-{ws_id}",
                    sequence=next_seq(),
                    archetype="worksheet_page",
                    data=ws,
                ))

        # ── 7. Rapid Response Page ─────────────────────────────────────────────
        failure_modes = arch.get("failure_modes", [])
        if failure_modes or arch.get("operating_constraints"):
            # Normalize failure modes into structured dicts
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
