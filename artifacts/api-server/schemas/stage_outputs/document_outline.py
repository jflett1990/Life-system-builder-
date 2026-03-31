"""Pydantic schema for the document_outline pipeline stage output."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class WorksheetPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    worksheet_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    purpose: str = ""
    section_count: int = 0
    estimated_field_count: int = 0


class ChapterPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    chapter_number: int
    domain_id: str = ""
    domain_name: str = Field(..., min_length=1)
    chapter_title: str = Field(..., min_length=1)
    chapter_purpose: str = ""
    key_topics: list[str] = []
    common_gap: str = ""
    cascade_triggers: list[str] = []
    worksheet_plan: list[WorksheetPlan] = []


class CascadeLink(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_domain: str = ""
    triggers: list[str] = []
    condition: str = ""


class DocumentOutlineOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    document_title: str = Field(..., min_length=1)
    document_subtitle: str = ""
    system_name: str = ""
    version: str = "1.0"
    total_chapters: int = 0
    master_operating_rules: list[str] = []
    cascade_chain: list[CascadeLink] = []
    disclaimer_required: bool = True
    introduction_text: str = ""
    chapters: list[ChapterPlan] = Field(..., min_length=1)
