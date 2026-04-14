"""Pydantic schemas for the chapter_expansion pipeline stage.

Four schemas:
  ChapterNarrativeOutput      — validates sub-call 1 (narrative-only pass) per chapter
  ChapterExpansionStructure   — validates sub-call 2 (structure pass) per chapter
  ExpandedChapter             — validates the merged result of both sub-calls
  ChapterExpansionOutput      — validates the accumulated output saved to the DB
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChapterField(BaseModel):
    model_config = ConfigDict(extra="allow")

    field_id: str = ""
    label: str = Field(..., min_length=1)
    type: str = "text"
    placeholder: str = ""
    options: list[str] = []
    required: bool = True
    validation_hint: str = ""


class ChapterSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    section_id: str = ""
    section_title: str = Field(..., min_length=1)
    instructions: str = ""
    fields: list[ChapterField] = []


class ChapterDecisionGate(BaseModel):
    model_config = ConfigDict(extra="allow")

    gate_id: str = ""
    gate_title: str = ""
    condition: str = ""
    pass_action: str = ""
    fail_action: str = ""
    blocks_completion: bool = False


class ExpandedWorksheet(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    purpose: str = ""
    estimated_completion_time: str = ""

    # Layout selector — determines which rendering template is used
    # "form"       — default: sections + fields (form-style write-in blocks)
    # "table"      — grid with column headers and blank rows (inventory/directory)
    # "checklist"  — column of checkbox items (audit/verification lists)
    # "two-column" — two parties/states side by side with shared fields
    layout: str = "form"

    # table layout
    table_columns: list[str] = []
    table_row_count: int = 12

    # checklist layout
    checklist_items: list[str] = []

    # two-column layout
    left_column_label: str = ""
    right_column_label: str = ""

    # form + two-column layouts
    sections: list[ChapterSection] = []
    decision_gates: list[ChapterDecisionGate] = []

    # repeat-use and cross-reference metadata
    repeat_use: bool = False
    cross_references: list[str] = []


# ── Sub-call 1: Narrative-only pass ───────────────────────────────────────────

class ChapterNarrativeOutput(BaseModel):
    """Schema for sub-call 1 of chapter expansion — narrative only.

    Used as schema_class_override in generate_structured_output so the
    model is validated purely on the presence of a non-empty narrative.
    All other fields are optional to avoid validation failures if the model
    returns minimal metadata alongside the narrative.
    """
    model_config = ConfigDict(extra="allow")

    chapter_number: int = 0
    domain_id: str = ""
    chapter_title: str = Field(..., min_length=1)
    narrative: str = Field(..., min_length=500)


# ── Sub-call 2: Structure pass ─────────────────────────────────────────────────

class ChapterExpansionStructure(BaseModel):
    """Schema for sub-call 2 of chapter expansion — structural elements only.

    Validates quick_reference_rules, cascade_triggers, scenario_scene, and
    success_metrics. Does NOT include narrative — that comes from sub-call 1.
    Used as schema_class_override in generate_structured_output.
    """
    model_config = ConfigDict(extra="allow")

    chapter_number: int = Field(..., ge=1)
    domain_id: str = Field(..., min_length=1)
    chapter_title: str = Field(..., min_length=1)
    chapter_opener: dict[str, Any] = Field(..., min_length=1)
    minimum_viable_actions: list[str] = Field(..., min_length=4)
    orientation_snapshot: str = Field(..., min_length=250)
    operational_sections: list[dict[str, Any]] = Field(..., min_length=4)
    worksheet_linkage: list[dict[str, str]] = Field(..., min_length=1)
    key_contacts: list[dict[str, str]] = []
    detailed_explanation: str = ""


# ── Merged per-chapter result ──────────────────────────────────────────────────

class ExpandedChapter(BaseModel):
    """Schema for the merged result of both sub-calls (narrative + structure).

    worksheets is kept as an optional field (default=[]) for backwards
    compatibility with projects run before the chapter_worksheets stage
    was introduced. New runs will have worksheets=[] here and worksheets
    populated in the separate chapter_worksheets stage output instead.
    """
    model_config = ConfigDict(extra="allow")

    chapter_number: int = 0
    domain_id: str = ""
    chapter_title: str = Field(..., min_length=1)
    narrative: str = Field(..., min_length=100)
    chapter_opener: dict[str, Any] = {}
    minimum_viable_actions: list[str] = []
    orientation_snapshot: str = ""
    operational_sections: list[dict[str, Any]] = []
    worksheets: list[ExpandedWorksheet] = []   # legacy / backwards compat only
    worksheet_linkage: list[dict[str, str]] = []
    key_contacts: list[dict[str, str]] = []
    detailed_explanation: str = ""


class ChapterExpansionOutput(BaseModel):
    """Accumulated output from all per-chapter loop calls — saved to DB."""
    model_config = ConfigDict(extra="allow")

    document_title: str = ""
    total_chapters: int = 0
    total_worksheets: int = 0
    chapters: list[ExpandedChapter] = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _compute_totals(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        chapters = values.get("chapters", [])
        if isinstance(chapters, list):
            values.setdefault("total_chapters", len(chapters))
            total_ws = sum(
                len(c.get("worksheets", [])) if isinstance(c, dict) else 0
                for c in chapters
            )
            values.setdefault("total_worksheets", total_ws)
        return values
