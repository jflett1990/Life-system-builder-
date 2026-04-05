"""Pydantic schemas for the chapter_worksheets pipeline stage.

Two schemas:
  ChapterWorksheetsOutput      — validates each per-chapter LLM call during the loop
  ChapterWorksheetsStageOutput — validates the accumulated output saved to the DB
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

# Reuse worksheet component schemas from chapter_expansion
from schemas.stage_outputs.chapter_expansion import ExpandedWorksheet


class ChapterWorksheetsOutput(BaseModel):
    """Schema for a single chapter worksheets call (per-domain loop)."""
    model_config = ConfigDict(extra="allow")

    chapter_number: int = 0
    domain_id: str = ""
    chapter_title: str = Field(..., min_length=1)
    worksheets: list[ExpandedWorksheet] = Field(..., min_length=1)


class ChapterWorksheetsStageOutput(BaseModel):
    """Accumulated output from all per-chapter worksheet calls — saved to DB."""
    model_config = ConfigDict(extra="allow")

    total_chapters: int = 0
    total_worksheets: int = 0
    chapters: list[ChapterWorksheetsOutput] = Field(..., min_length=1)

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
