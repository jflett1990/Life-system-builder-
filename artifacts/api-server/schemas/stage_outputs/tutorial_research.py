"""
Pydantic schema for the tutorial_research stage output (Stack Research).

Contract: tutorial_research.json
Required fields: research_summary, facts, common_errors, key_commands

The research grounds every downstream stage in verifiable stack facts:
version baselines, key commands with expected outputs, common errors with
fixes, and canonical references. Low-confidence facts surface as
open_questions so writers know what to verify.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResearchFact(BaseModel):
    model_config = ConfigDict(extra="allow")

    fact_id: str = ""
    claim: str = Field(..., min_length=1)
    category: str = ""           # version | command | configuration | gotcha | concept | security | compatibility
    applies_to_modules: list[str] = []
    confidence: str = "medium"   # high | medium | low
    source_hint: str = ""


class VersionBaseline(BaseModel):
    model_config = ConfigDict(extra="allow")

    tool: str = Field(..., min_length=1)
    minimum_version: str = ""
    notes: str = ""


class CommonError(BaseModel):
    model_config = ConfigDict(extra="allow")

    symptom: str = Field(..., min_length=1)
    cause: str = ""
    fix: str = ""
    applies_to_modules: list[str] = []


class KeyCommand(BaseModel):
    model_config = ConfigDict(extra="allow")

    command: str = Field(..., min_length=1)
    run_from: str = ""
    purpose: str = ""
    expected_output: str = ""
    applies_to_modules: list[str] = []


class ReferenceLink(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str = ""
    url: str = ""
    why: str = ""


class TutorialResearchOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    research_summary: str = Field(..., min_length=1)
    facts: list[ResearchFact] = Field(..., min_length=1)
    version_baselines: list[VersionBaseline] = []
    common_errors: list[CommonError] = []
    key_commands: list[KeyCommand] = []
    reference_links: list[ReferenceLink] = []
    open_questions: list[str] = []
