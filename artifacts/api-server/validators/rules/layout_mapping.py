"""
Stage 3 — Layout Mapping rule set.

Rules:
  LAYOUT_REQUIRED_FIELD        fatal  — required field absent or empty
  LAYOUT_NO_SECTIONS           fatal  — sections array empty
  LAYOUT_EMPTY_CONTENT_SLOTS   error  — a section has zero content_slots
  LAYOUT_INVALID_SECTION_TYPE  error  — section_type not in valid set
  LAYOUT_MISSING_SOURCE_REF    error  — section with type 'worksheet' or 'domain-overview'
                                        has no source.reference_id
"""
from __future__ import annotations

from typing import Any

from validators.defect import Defect, Severity
from validators.rules.base import BaseRule

STAGE = "layout_mapping"

REQUIRED_FIELDS = ["document_title", "sections", "navigation_map"]

VALID_SECTION_TYPES = {
    "cover", "toc", "introduction", "domain-overview",
    "worksheet", "appendix", "reference",
}

CONTENT_LINKED_TYPES = {"domain-overview", "worksheet"}


class RequiredFieldRule(BaseRule):
    rule_id  = "LAYOUT_REQUIRED_FIELD"
    severity = Severity.fatal
    code     = "LAYOUT_REQUIRED_FIELD"
    title    = "Required Layout Field Missing or Empty"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for f in REQUIRED_FIELDS:
            val = stage_output.get(f)
            if val is None:
                defects.append(self._defect(
                    stage=STAGE, field_path=f, evidence="(field absent)",
                    message=f"Required field '{f}' is absent from layout mapping output.",
                    required_fix=f"Re-run stage 3 to populate '{f}'.",
                ))
            elif isinstance(val, (str, list, dict)) and not val:
                defects.append(self._defect(
                    stage=STAGE, field_path=f, evidence="(empty)",
                    message=f"Required field '{f}' is empty.",
                    required_fix=f"Re-run stage 3 with correct upstream context.",
                ))
        return defects


class NoSectionsRule(BaseRule):
    rule_id  = "LAYOUT_NO_SECTIONS"
    severity = Severity.fatal
    code     = "LAYOUT_NO_SECTIONS"
    title    = "Layout Has Zero Sections"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        sections = stage_output.get("sections", [])
        if not isinstance(sections, list) or len(sections) == 0:
            return [self._defect(
                stage=STAGE, field_path="sections",
                evidence=str(sections),
                message=(
                    "The sections array is empty. A layout with zero sections cannot "
                    "drive the render stage — the render blueprint has nothing to reference."
                ),
                required_fix="Re-run stage 3. Minimum 3 sections (cover, at least one domain, one worksheet) required.",
            )]
        return []


class EmptyContentSlotsRule(BaseRule):
    rule_id  = "LAYOUT_EMPTY_CONTENT_SLOTS"
    severity = Severity.error
    code     = "LAYOUT_EMPTY_CONTENT_SLOTS"
    title    = "Layout Section Has No Content Slots"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, sec in enumerate(stage_output.get("sections", [])):
            if not isinstance(sec, dict):
                continue
            slots = sec.get("content_slots", [])
            if not isinstance(slots, list) or len(slots) == 0:
                sec_id = sec.get("section_id", f"index-{i}")
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"sections[{i}].content_slots",
                    evidence=f"section_id='{sec_id}', type='{sec.get('section_type', '?')}', title='{sec.get('title', '?')}'",
                    message=(
                        f"Section '{sec_id}' ({sec.get('title', 'untitled')}) has no content_slots. "
                        "The render blueprint stage needs content_slots to know what to render "
                        "in each section. An empty section produces a blank page."
                    ),
                    required_fix=(
                        f"Add at least 1 content_slot to section '{sec_id}'. "
                        "Each slot must reference a source_field from the upstream stage output."
                    ),
                ))
        return defects


class InvalidSectionTypeRule(BaseRule):
    rule_id  = "LAYOUT_INVALID_SECTION_TYPE"
    severity = Severity.error
    code     = "LAYOUT_INVALID_SECTION_TYPE"
    title    = "Layout Section Has Invalid or Unknown section_type"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, sec in enumerate(stage_output.get("sections", [])):
            if not isinstance(sec, dict):
                continue
            sec_type = sec.get("section_type", "")
            if sec_type not in VALID_SECTION_TYPES:
                sec_id = sec.get("section_id", f"index-{i}")
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"sections[{i}].section_type",
                    evidence=f"'{sec_type}' — valid types: {sorted(VALID_SECTION_TYPES)}",
                    message=(
                        f"Section '{sec_id}' has section_type='{sec_type}' which is not "
                        f"in the valid type set. The render engine cannot map an unknown type to a template."
                    ),
                    required_fix=(
                        f"Change section_type to one of: {', '.join(sorted(VALID_SECTION_TYPES))}."
                    ),
                ))
        return defects


class MissingSourceRefRule(BaseRule):
    rule_id  = "LAYOUT_MISSING_SOURCE_REF"
    severity = Severity.error
    code     = "LAYOUT_MISSING_SOURCE_REF"
    title    = "Content-Linked Section Missing Source Reference"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, sec in enumerate(stage_output.get("sections", [])):
            if not isinstance(sec, dict):
                continue
            if sec.get("section_type") not in CONTENT_LINKED_TYPES:
                continue
            source = sec.get("source", {})
            if not isinstance(source, dict) or not source.get("reference_id"):
                sec_id = sec.get("section_id", f"index-{i}")
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"sections[{i}].source.reference_id",
                    evidence=f"section_id='{sec_id}', type='{sec.get('section_type')}'",
                    message=(
                        f"Section '{sec_id}' is of type '{sec.get('section_type')}' which requires "
                        "a source.reference_id linking it to an upstream domain or worksheet ID. "
                        "Without this reference the render engine cannot fetch the correct data."
                    ),
                    required_fix=(
                        f"Set source.reference_id on section '{sec_id}' to the matching "
                        "domain ID (e.g. 'domain-01') or worksheet ID (e.g. 'ws-01')."
                    ),
                ))
        return defects


LAYOUT_MAPPING_RULES: list[BaseRule] = [
    RequiredFieldRule(),
    NoSectionsRule(),
    EmptyContentSlotsRule(),
    InvalidSectionTypeRule(),
    MissingSourceRefRule(),
]
