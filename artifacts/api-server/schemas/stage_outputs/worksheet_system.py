"""
Pydantic schema for the worksheet_system stage output.

Contract: worksheet_system.json
Required fields: worksheet_system_name, worksheets, completion_sequence
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


class FieldDef(BaseModel):
    model_config = ConfigDict(extra="allow")

    field_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    type: str = "text"
    options: list[str] = []
    required: bool = True


class WorksheetSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    section_title: str = Field(..., min_length=1)
    fields: list[FieldDef] = []


class DecisionGate(BaseModel):
    model_config = ConfigDict(extra="allow")

    gate_id: str = Field(..., min_length=1)
    condition: str = Field(..., min_length=1)
    pass_action: str = ""
    fail_action: str = ""


class Worksheet(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    sections: list[WorksheetSection] = []
    decision_gates: list[DecisionGate] = []


class WorksheetSystemOutput(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    worksheet_system_name: str = Field(..., min_length=1)
    worksheets: list[Worksheet] = Field(..., min_length=1)
    completion_sequence: list[str] = Field(..., min_length=1)

    @field_validator("completion_sequence", mode="before")
    @classmethod
    def _require_strings(cls, v: list) -> list:
        if isinstance(v, list):
            return [str(item) for item in v if item]
        return v
