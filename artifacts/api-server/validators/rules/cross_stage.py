"""
Cross-stage consistency rules.

These rules compare outputs across multiple stages for referential integrity.
They run after all per-stage rules complete.

Rules:
  CROSS_WORKSHEET_DOMAIN_REF    error — worksheet domain_id not found in architecture domains
  CROSS_LAYOUT_CONTENT_REF      error — layout section source.reference_id not found in
                                        worksheet IDs or domain IDs
  CROSS_RENDER_SECTION_REF      error — render directive section_id not found in layout sections
  CROSS_DOMAIN_COUNT_MISMATCH   warning — number of worksheets < number of control domains
"""
from __future__ import annotations

from typing import Any

from validators.defect import Defect, Severity
from validators.rules.base import BaseRule

STAGE = "cross_stage"


def _extract_domain_ids(arch: dict) -> set[str]:
    return {
        d.get("id")
        for d in arch.get("control_domains", [])
        if isinstance(d, dict) and d.get("id")
    }


def _extract_worksheet_ids(ws_system: dict) -> set[str]:
    return {
        ws.get("id")
        for ws in ws_system.get("worksheets", [])
        if isinstance(ws, dict) and ws.get("id")
    }


def _extract_layout_section_ids(layout: dict) -> set[str]:
    return {
        s.get("section_id")
        for s in layout.get("sections", [])
        if isinstance(s, dict) and s.get("section_id")
    }


class WorksheetDomainRefRule(BaseRule):
    """Each worksheet must reference a domain_id that exists in the system architecture."""
    rule_id  = "CROSS_WORKSHEET_DOMAIN_REF"
    severity = Severity.error
    code     = "CROSS_WORKSHEET_DOMAIN_REF"
    title    = "Worksheet References Domain ID Not in System Architecture"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        arch = context.get("system_architecture")
        ws_system = context.get("worksheet_system")
        if not arch or not ws_system:
            return []

        domain_ids = _extract_domain_ids(arch)
        if not domain_ids:
            return []

        defects = []
        for i, ws in enumerate(ws_system.get("worksheets", [])):
            if not isinstance(ws, dict):
                continue
            ws_domain_id = ws.get("domain_id")
            if ws_domain_id and ws_domain_id not in domain_ids:
                defects.append(self._defect(
                    stage="worksheet_system",
                    field_path=f"worksheets[{i}].domain_id",
                    evidence=f"'{ws_domain_id}' not in architecture domain IDs: {sorted(domain_ids)}",
                    message=(
                        f"Worksheet '{ws.get('id', i)}' references domain_id='{ws_domain_id}' "
                        "which does not exist in the system_architecture control_domains. "
                        "This broken reference means the worksheet is not grounded in the system design."
                    ),
                    required_fix=(
                        f"Change domain_id on worksheet '{ws.get('id', i)}' to one of the "
                        f"valid domain IDs: {sorted(domain_ids)}."
                    ),
                ))
        return defects


class LayoutContentRefRule(BaseRule):
    """Layout sections of type worksheet/domain-overview must reference valid IDs."""
    rule_id  = "CROSS_LAYOUT_CONTENT_REF"
    severity = Severity.error
    code     = "CROSS_LAYOUT_CONTENT_REF"
    title    = "Layout Section References Worksheet or Domain ID That Does Not Exist"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        arch = context.get("system_architecture")
        ws_system = context.get("worksheet_system")
        layout = context.get("layout_mapping")
        if not arch or not ws_system or not layout:
            return []

        valid_refs = _extract_domain_ids(arch) | _extract_worksheet_ids(ws_system)
        defects = []

        for i, sec in enumerate(layout.get("sections", [])):
            if not isinstance(sec, dict):
                continue
            if sec.get("section_type") not in {"worksheet", "domain-overview"}:
                continue
            source = sec.get("source", {})
            if not isinstance(source, dict):
                continue
            ref_id = source.get("reference_id")
            if ref_id and ref_id not in valid_refs:
                defects.append(self._defect(
                    stage="layout_mapping",
                    field_path=f"sections[{i}].source.reference_id",
                    evidence=f"'{ref_id}' not in valid refs: {sorted(valid_refs)}",
                    message=(
                        f"Layout section '{sec.get('section_id', i)}' references "
                        f"'{ref_id}' which is not a valid domain ID or worksheet ID. "
                        "The render stage cannot look up this section's content."
                    ),
                    required_fix=(
                        f"Change reference_id to one of: {sorted(valid_refs)}."
                    ),
                ))
        return defects


class RenderSectionRefRule(BaseRule):
    """Render directives must reference section_ids that exist in the layout."""
    rule_id  = "CROSS_RENDER_SECTION_REF"
    severity = Severity.error
    code     = "CROSS_RENDER_SECTION_REF"
    title    = "Render Directive References Section ID Not in Layout Mapping"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        layout = context.get("layout_mapping")
        blueprint = context.get("render_blueprint")
        if not layout or not blueprint:
            return []

        layout_section_ids = _extract_layout_section_ids(layout)
        defects = []

        for i, directive in enumerate(blueprint.get("render_directives", [])):
            if not isinstance(directive, dict):
                continue
            sec_id = directive.get("section_id")
            if sec_id and layout_section_ids and sec_id not in layout_section_ids:
                defects.append(self._defect(
                    stage="render_blueprint",
                    field_path=f"render_directives[{i}].section_id",
                    evidence=f"'{sec_id}' not in layout sections: {sorted(layout_section_ids)}",
                    message=(
                        f"Render directive[{i}] references section_id='{sec_id}' "
                        "which does not exist in the layout_mapping. "
                        "The render engine will error when it cannot find this section."
                    ),
                    required_fix=(
                        f"Change section_id to one of the layout section IDs: "
                        f"{sorted(layout_section_ids)}."
                    ),
                ))
        return defects


class DomainWorksheetCountRule(BaseRule):
    """Each control domain should have a corresponding worksheet."""
    rule_id  = "CROSS_DOMAIN_COUNT_MISMATCH"
    severity = Severity.warning
    code     = "CROSS_DOMAIN_COUNT_MISMATCH"
    title    = "Fewer Worksheets Than Control Domains"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        arch = context.get("system_architecture")
        ws_system = context.get("worksheet_system")
        if not arch or not ws_system:
            return []

        domain_count = len(arch.get("control_domains", []))
        worksheet_count = len(ws_system.get("worksheets", []))

        if worksheet_count < domain_count:
            return [self._defect(
                stage="worksheet_system",
                field_path="worksheets",
                evidence=f"{worksheet_count} worksheet(s) for {domain_count} domain(s)",
                message=(
                    f"There are {domain_count} control domains but only {worksheet_count} "
                    "worksheet(s). Each control domain should produce exactly one worksheet. "
                    "Uncovered domains have no operational capture tool."
                ),
                required_fix=(
                    f"Add {domain_count - worksheet_count} more worksheet(s) to cover all "
                    "control domains. Each worksheet's domain_id must match a domain ID from "
                    "the system architecture."
                ),
                severity=Severity.warning,
                blocked_handoff=False,
            )]
        return []


CROSS_STAGE_RULES: list[BaseRule] = [
    WorksheetDomainRefRule(),
    LayoutContentRefRule(),
    RenderSectionRefRule(),
    DomainWorksheetCountRule(),
]
