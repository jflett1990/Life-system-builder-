"""Pydantic schemas for the appendix_builder pipeline stage.

Generates 3–5 appendix pages specific to the life event:
  - Glossary (15–25 domain terms with definitions)
  - When to Call a Professional (8–12 triggering situations)
  - Key Resources & Contacts (table of organizations/services)
  - Notes (blank ruled pages — no content schema needed, just a flag)
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GlossaryTerm(BaseModel):
    model_config = ConfigDict(extra="allow")

    term: str = Field(..., min_length=1)
    definition: str = Field(..., min_length=10)


class ProfessionalTrigger(BaseModel):
    model_config = ConfigDict(extra="allow")

    situation: str = Field(..., min_length=5)
    professional_type: str = Field(..., min_length=3)
    urgency: str = ""


class KeyResourceRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    organization: str = ""
    service: str = ""
    phone: str = ""
    website: str = ""
    hours: str = ""


class AppendixBuilderOutput(BaseModel):
    """Accumulated output from the appendix_builder stage — saved to DB."""
    model_config = ConfigDict(extra="allow")

    life_event: str = ""
    glossary_terms: list[GlossaryTerm] = Field(..., min_length=10)
    professional_triggers: list[ProfessionalTrigger] = Field(..., min_length=5)
    key_resources: list[KeyResourceRow] = []
    include_notes_pages: bool = True
    notes_page_count: int = 3
