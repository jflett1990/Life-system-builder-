"""
Stage 4 — Render Blueprint rule set.

Rules:
  RENDER_REQUIRED_FIELD        fatal  — required field absent or empty
  RENDER_NO_DIRECTIVES         fatal  — render_directives array empty
  RENDER_MISSING_THEME_COLORS  error  — theme.color_palette missing required tokens
  RENDER_VAGUE_COMPONENT       error  — a slot uses an unrecognised component type
  RENDER_SLOT_NO_DATA_PATH     error  — a slot has neither content nor data_path
  RENDER_VAGUE_SPEC            error  — theme typography or spacing is absent (vague render spec)
"""
from __future__ import annotations

from typing import Any

from validators.defect import Defect, Severity
from validators.rules.base import BaseRule

STAGE = "render_blueprint"

REQUIRED_FIELDS = ["blueprint_name", "theme", "render_directives"]

REQUIRED_COLOR_TOKENS = [
    "primary", "secondary", "background", "text_primary",
]

VALID_COMPONENTS = {
    "heading-1", "heading-2", "body-paragraph", "field-row",
    "decision-gate-block", "milestone-timeline", "role-table",
    "criteria-checklist", "divider", "document-title", "section-heading",
    "body-text", "field-grid", "milestone-list", "criteria-list",
    "page-footer", "reference-table",
}


class RequiredFieldRule(BaseRule):
    rule_id  = "RENDER_REQUIRED_FIELD"
    severity = Severity.fatal
    code     = "RENDER_REQUIRED_FIELD"
    title    = "Required Render Blueprint Field Missing or Empty"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for f in REQUIRED_FIELDS:
            val = stage_output.get(f)
            if val is None:
                defects.append(self._defect(
                    stage=STAGE, field_path=f, evidence="(field absent)",
                    message=f"Required render blueprint field '{f}' is absent.",
                    required_fix=f"Re-run stage 4. The model must produce '{f}'.",
                ))
            elif isinstance(val, (str, list, dict)) and not val:
                defects.append(self._defect(
                    stage=STAGE, field_path=f, evidence="(empty)",
                    message=f"Required render blueprint field '{f}' is empty.",
                    required_fix="Re-run stage 4 with full upstream context.",
                ))
        return defects


class NoDirectivesRule(BaseRule):
    rule_id  = "RENDER_NO_DIRECTIVES"
    severity = Severity.fatal
    code     = "RENDER_NO_DIRECTIVES"
    title    = "Render Blueprint Has Zero Directives"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        directives = stage_output.get("render_directives", [])
        if not isinstance(directives, list) or len(directives) == 0:
            return [self._defect(
                stage=STAGE, field_path="render_directives",
                evidence=str(directives),
                message=(
                    "render_directives is empty. Without directives the template engine has "
                    "no instructions — it cannot produce any rendered output."
                ),
                required_fix="Re-run stage 4. One directive per layout section is the minimum.",
            )]
        return []


class MissingThemeColorsRule(BaseRule):
    rule_id  = "RENDER_MISSING_THEME_COLORS"
    severity = Severity.error
    code     = "RENDER_MISSING_THEME_COLORS"
    title    = "Theme Color Palette Missing Required Tokens"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        theme = stage_output.get("theme", {})
        if not isinstance(theme, dict):
            return [self._defect(
                stage=STAGE, field_path="theme",
                evidence=str(theme),
                message="theme field is not a valid object.",
                required_fix="Re-run stage 4. theme must be an object containing color_palette and typography.",
            )]
        palette = theme.get("color_palette", {})
        if not isinstance(palette, dict):
            return [self._defect(
                stage=STAGE, field_path="theme.color_palette",
                evidence=str(palette),
                message="theme.color_palette is absent or not an object.",
                required_fix="Re-run stage 4. theme.color_palette must be an object with hex color values.",
            )]
        for token in REQUIRED_COLOR_TOKENS:
            if not palette.get(token):
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"theme.color_palette.{token}",
                    evidence=f"'{token}' missing from palette: {list(palette.keys())}",
                    message=(
                        f"Required color token '{token}' is absent from theme.color_palette. "
                        "The CSS token system will fall back to hardcoded defaults, "
                        "producing a document that does not match the intended theme."
                    ),
                    required_fix=f"Add a hex color value for '{token}' in theme.color_palette.",
                    severity=Severity.warning,
                    blocked_handoff=False,
                ))
        return defects


class VagueComponentRule(BaseRule):
    rule_id  = "RENDER_VAGUE_COMPONENT"
    severity = Severity.error
    code     = "RENDER_VAGUE_COMPONENT"
    title    = "Render Directive Slot Uses Unrecognised Component Type"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, directive in enumerate(stage_output.get("render_directives", [])):
            if not isinstance(directive, dict):
                continue
            for j, slot in enumerate(directive.get("slots", [])):
                if not isinstance(slot, dict):
                    continue
                component = slot.get("component", "")
                if component and component not in VALID_COMPONENTS:
                    defects.append(self._defect(
                        stage=STAGE,
                        field_path=f"render_directives[{i}].slots[{j}].component",
                        evidence=f"'{component}' — valid: {sorted(VALID_COMPONENTS)}",
                        message=(
                            f"Slot at directive[{i}].slots[{j}] uses component='{component}' "
                            "which is not in the valid component registry. "
                            "The template engine cannot render an unknown component type."
                        ),
                        required_fix=(
                            f"Replace '{component}' with one of the valid component types. "
                            "Most common for data: 'field-row', 'role-table', 'criteria-checklist'."
                        ),
                    ))
        return defects


class VagueRenderSpecRule(BaseRule):
    rule_id  = "RENDER_VAGUE_SPEC"
    severity = Severity.error
    code     = "RENDER_VAGUE_SPEC"
    title    = "Render Blueprint Has Vague Specification — Missing Typography or Spacing"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        theme = stage_output.get("theme", {})
        if not isinstance(theme, dict):
            return []
        if not theme.get("typography"):
            defects.append(self._defect(
                stage=STAGE,
                field_path="theme.typography",
                evidence="theme.typography absent or empty",
                message=(
                    "theme.typography is absent. A vague render spec produces documents where "
                    "the renderer falls back to browser defaults — the output is uncontrolled "
                    "and will not match the design intent."
                ),
                required_fix="Add theme.typography with at minimum heading_font, body_font, and base_size_px.",
            ))
        if not theme.get("spacing"):
            defects.append(self._defect(
                stage=STAGE,
                field_path="theme.spacing",
                evidence="theme.spacing absent or empty",
                message="theme.spacing is absent. Page margins and section gaps will use CSS fallbacks.",
                required_fix="Add theme.spacing with page_margin_mm and section_gap_px.",
                severity=Severity.warning,
                blocked_handoff=False,
            ))
        return defects


RENDER_BLUEPRINT_RULES: list[BaseRule] = [
    RequiredFieldRule(),
    NoDirectivesRule(),
    MissingThemeColorsRule(),
    VagueComponentRule(),
    VagueRenderSpecRule(),
]
