"""
Pydantic schema for the worksheet_system stage output.

Contract: worksheet_system.json
Required fields: worksheet_system_name, worksheets, completion_sequence
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
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
    # domain may appear as "domain", "domain_name", "domain_id" depending on which
    # version of the contract the model followed.  Make it optional so the schema
    # never triggers a correction retry over a missing/wrong-type domain label.
    domain: str | None = Field(default=None)
    purpose: str = Field(..., min_length=1)
    sections: list[WorksheetSection] = []
    decision_gates: list[DecisionGate] = []

    @model_validator(mode="before")
    @classmethod
    def _coerce_domain(cls, values: Any) -> Any:
        """Promote domain_name or domain_id into domain if domain is absent."""
        if not isinstance(values, dict):
            return values
        if not values.get("domain"):
            # Prefer domain_name, fall back to domain_id, then empty
            values["domain"] = (
                values.get("domain_name")
                or values.get("domain_id")
                or ""
            )
        return values


class WorksheetSystemOutput(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    worksheet_system_name: str = Field(..., min_length=1)
    worksheets: list[Worksheet] = Field(..., min_length=1)
    completion_sequence: list[str] = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _unwrap_nested(cls, values: Any) -> Any:
        """
        Handle cases where the LLM wraps the response inside a named object.

        Common patterns produced by the model:
          { "worksheet_system": { ... } }   → unwrap
          { "system": { ... } }             → unwrap
          { "data": { ... } }               → unwrap
        """
        if not isinstance(values, dict):
            return values

        # If the required fields are already at the top level, nothing to do
        _required = {"worksheet_system_name", "worksheets", "completion_sequence"}
        if _required & values.keys():
            return values

        # Try common wrapper keys
        for wrapper_key in ("worksheet_system", "system", "data", "output"):
            inner = values.get(wrapper_key)
            if isinstance(inner, dict) and (_required & inner.keys()):
                return inner

        # If there's exactly one key and its value is a dict, try unwrapping it
        if len(values) == 1:
            only_val = next(iter(values.values()))
            if isinstance(only_val, dict) and (_required & only_val.keys()):
                return only_val

        return values

    @field_validator("completion_sequence", mode="before")
    @classmethod
    def _require_strings(cls, v: list) -> list:
        if isinstance(v, list):
            return [str(item) for item in v if item]
        return v
