"""
Stage 2 — Worksheet System rule set.

Rules:
  WS_REQUIRED_FIELD           fatal   — top-level required field absent/empty
  WS_NO_WORKSHEETS            fatal   — worksheets array empty
  WS_DECORATIVE               fatal   — worksheet has < 3 fields total across all sections
  WS_GENERIC_LABELS           fatal   — >50% of field labels are domain-generic terms
  WS_ADVICE_IN_LABELS         error   — field labels contain advisory verbs (Make sure, Consider...)
  WS_DOMAIN_UNLINKED          error   — worksheet domain_id not present or not matched (cross-stage)
  WS_SEQUENCE_MISMATCH        error   — completion_sequence IDs don't match actual worksheet IDs
  WS_NO_DECISION_GATES        warning — worksheet has zero decision_gates

Generic label detection:
  Labels are considered generic if they match common content-agnostic terms like
  "Name", "Date", "Notes", "Comments", "Details" with no qualifying noun.
"""
from __future__ import annotations

import re
from typing import Any

from validators.defect import Defect, Severity
from validators.rules.base import BaseRule

STAGE = "worksheet_system"

REQUIRED_FIELDS = ["worksheet_system_name", "worksheets", "completion_sequence"]

GENERIC_LABEL_TERMS = re.compile(
    r"^(name|date|notes?|comments?|details?|information|info|other|additional|"
    r"description|more|remarks?|misc|miscellaneous|text|input|value|data|"
    r"field|entry|answer|response|content)$",
    re.IGNORECASE,
)

ADVICE_LABEL_PATTERN = re.compile(
    r"^(make sure|ensure|consider|try to|remember|don.t forget|be sure|"
    r"check that|verify that|confirm that|note that|please)",
    re.IGNORECASE,
)

VALID_FIELD_TYPES = {"text", "date", "boolean", "number", "select", "multi-select", "textarea"}


def _collect_fields(worksheet: dict) -> list[dict]:
    fields = []
    for section in worksheet.get("sections", []):
        fields.extend(section.get("fields", []))
    return fields


class RequiredFieldRule(BaseRule):
    rule_id  = "WS_REQUIRED_FIELD"
    severity = Severity.fatal
    code     = "WS_REQUIRED_FIELD"
    title    = "Required Worksheet System Field Missing or Empty"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for f in REQUIRED_FIELDS:
            val = stage_output.get(f)
            if val is None:
                defects.append(self._defect(
                    stage=STAGE, field_path=f, evidence="(field absent)",
                    message=f"Required field '{f}' is completely absent from worksheet system output.",
                    required_fix=f"Re-run stage 2. The model must produce '{f}'.",
                ))
            elif isinstance(val, (str, list, dict)) and not val:
                defects.append(self._defect(
                    stage=STAGE, field_path=f, evidence="(empty)",
                    message=f"Required field '{f}' is present but empty.",
                    required_fix=f"Re-run stage 2 with upstream context to populate '{f}'.",
                ))
        return defects


class NoWorksheetsRule(BaseRule):
    rule_id  = "WS_NO_WORKSHEETS"
    severity = Severity.fatal
    code     = "WS_NO_WORKSHEETS"
    title    = "Worksheet Array Is Empty"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        worksheets = stage_output.get("worksheets", [])
        if not isinstance(worksheets, list) or len(worksheets) == 0:
            return [self._defect(
                stage=STAGE, field_path="worksheets",
                evidence=str(worksheets),
                message=(
                    "The worksheets array is empty. Zero worksheets means the pipeline "
                    "produced no operational capture tools — the output is non-functional."
                ),
                required_fix=(
                    "Re-run stage 2. One worksheet per control domain is required. "
                    "Ensure stage 1 upstream output is passed correctly."
                ),
            )]
        return []


class DecorativeWorksheetRule(BaseRule):
    rule_id  = "WS_DECORATIVE"
    severity = Severity.fatal
    code     = "WS_DECORATIVE"
    title    = "Worksheet Is Decorative — Insufficient Field Count"
    blocked_handoff = True

    MIN_FIELDS = 3

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, ws in enumerate(stage_output.get("worksheets", [])):
            if not isinstance(ws, dict):
                continue
            fields = _collect_fields(ws)
            if len(fields) < self.MIN_FIELDS:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"worksheets[{i}].sections",
                    evidence=(
                        f"Worksheet '{ws.get('id', i)}' — '{ws.get('title', 'untitled')}' "
                        f"has {len(fields)} field(s) across all sections"
                    ),
                    message=(
                        f"Worksheet '{ws.get('id', i)}' ({ws.get('title', 'untitled')}) contains "
                        f"only {len(fields)} field(s). Minimum is {self.MIN_FIELDS}. "
                        "A worksheet with fewer than 3 fields cannot function as an operational capture tool — "
                        "it is decorative structure."
                    ),
                    required_fix=(
                        f"Rewrite worksheet '{ws.get('id', i)}' with at minimum 3 domain-specific "
                        f"fields across its sections. Each section must capture a distinct "
                        "decision or data point relevant to its control domain."
                    ),
                ))
        return defects


class GenericLabelsRule(BaseRule):
    rule_id  = "WS_GENERIC_LABELS"
    severity = Severity.fatal
    code     = "WS_GENERIC_LABELS"
    title    = "Worksheet Fields Use Generic, Domain-Agnostic Labels"
    blocked_handoff = True

    THRESHOLD = 0.5  # if more than 50% of labels are generic, fail

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, ws in enumerate(stage_output.get("worksheets", [])):
            if not isinstance(ws, dict):
                continue
            all_fields = _collect_fields(ws)
            if not all_fields:
                continue
            generic_fields = [
                f for f in all_fields
                if isinstance(f.get("label"), str)
                and GENERIC_LABEL_TERMS.match(f["label"].strip())
            ]
            ratio = len(generic_fields) / len(all_fields)
            if ratio > self.THRESHOLD:
                generic_labels = [f.get("label", "?") for f in generic_fields]
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"worksheets[{i}].sections[*].fields",
                    evidence=(
                        f"{len(generic_fields)}/{len(all_fields)} fields are generic: "
                        + ", ".join(f"'{l}'" for l in generic_labels[:6])
                    ),
                    message=(
                        f"Worksheet '{ws.get('id', i)}' ({ws.get('title', 'untitled')}) has "
                        f"{len(generic_fields)} out of {len(all_fields)} fields ({ratio:.0%}) "
                        "with generic, content-agnostic labels. "
                        "Generic labels (Name, Date, Notes, etc.) are hard failures — "
                        "they indicate the worksheet was not derived from the upstream system "
                        "architecture and cannot capture domain-specific operational decisions."
                    ),
                    required_fix=(
                        "Rewrite all generic field labels to be specific to the control domain. "
                        "For example: 'Date' → 'Estate Filing Deadline', "
                        "'Name' → 'Beneficiary Legal Name', 'Notes' → 'Probate Court Observations'."
                    ),
                ))
        return defects


class AdviceInLabelsRule(BaseRule):
    rule_id  = "WS_ADVICE_IN_LABELS"
    severity = Severity.error
    code     = "WS_ADVICE_IN_LABELS"
    title    = "Field Labels Contain Advisory Language"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, ws in enumerate(stage_output.get("worksheets", [])):
            if not isinstance(ws, dict):
                continue
            for j, section in enumerate(ws.get("sections", [])):
                for k, f in enumerate(section.get("fields", [])):
                    label = f.get("label", "")
                    if isinstance(label, str) and ADVICE_LABEL_PATTERN.match(label.strip()):
                        defects.append(self._defect(
                            stage=STAGE,
                            field_path=f"worksheets[{i}].sections[{j}].fields[{k}].label",
                            evidence=label,
                            message=(
                                f"Field label '{label}' starts with an advisory verb. "
                                "Field labels must be data capture prompts (nouns or noun phrases), "
                                "not instructions to the operator."
                            ),
                            required_fix=(
                                f"Rename '{label}' to a noun phrase that names what is being "
                                "captured — e.g. 'Make sure to document beneficiaries' → 'Beneficiary List'."
                            ),
                        ))
        return defects


class SequenceMismatchRule(BaseRule):
    rule_id  = "WS_SEQUENCE_MISMATCH"
    severity = Severity.error
    code     = "WS_SEQUENCE_MISMATCH"
    title    = "Completion Sequence Contains Invalid Worksheet IDs"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        worksheets = stage_output.get("worksheets", [])
        sequence = stage_output.get("completion_sequence", [])
        if not isinstance(worksheets, list) or not isinstance(sequence, list):
            return []
        actual_ids = {ws.get("id") for ws in worksheets if isinstance(ws, dict) and ws.get("id")}
        for seq_id in sequence:
            if seq_id not in actual_ids:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path="completion_sequence",
                    evidence=f"'{seq_id}' not in {sorted(actual_ids)}",
                    message=(
                        f"completion_sequence references worksheet ID '{seq_id}' which does not "
                        "exist in the worksheets array. This would cause the frontend to render "
                        "a broken completion flow."
                    ),
                    required_fix=(
                        f"Remove '{seq_id}' from completion_sequence or add a worksheet "
                        f"with id='{seq_id}' to the worksheets array."
                    ),
                ))
        # Also flag worksheets missing from the sequence
        for ws_id in actual_ids:
            if ws_id not in sequence:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path="completion_sequence",
                    evidence=f"'{ws_id}' in worksheets but not in sequence",
                    message=f"Worksheet '{ws_id}' exists but is not included in completion_sequence.",
                    required_fix=f"Add '{ws_id}' to completion_sequence in the correct position.",
                    severity=Severity.warning,
                    blocked_handoff=False,
                ))
        return defects


class NoDecisionGatesRule(BaseRule):
    rule_id  = "WS_NO_DECISION_GATES"
    severity = Severity.warning
    code     = "WS_NO_DECISION_GATES"
    title    = "Worksheet Has No Decision Gates"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, ws in enumerate(stage_output.get("worksheets", [])):
            if not isinstance(ws, dict):
                continue
            gates = ws.get("decision_gates", [])
            if not isinstance(gates, list) or len(gates) == 0:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"worksheets[{i}].decision_gates",
                    evidence=f"Worksheet '{ws.get('id', i)}' — 0 decision gates",
                    message=(
                        f"Worksheet '{ws.get('id', i)}' ({ws.get('title', 'untitled')}) "
                        "has no decision gates. Decision gates are required for operational "
                        "worksheets that govern process control."
                    ),
                    required_fix=(
                        "Add at least 1 decision gate defining a binary condition that "
                        "determines whether this worksheet's domain is complete."
                    ),
                    severity=Severity.warning,
                    blocked_handoff=False,
                ))
        return defects


WORKSHEET_SYSTEM_RULES: list[BaseRule] = [
    RequiredFieldRule(),
    NoWorksheetsRule(),
    DecorativeWorksheetRule(),
    GenericLabelsRule(),
    AdviceInLabelsRule(),
    SequenceMismatchRule(),
    NoDecisionGatesRule(),
]
