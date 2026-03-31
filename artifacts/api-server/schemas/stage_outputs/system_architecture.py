"""
Pydantic schema for the system_architecture stage output.

Contract: system_architecture.json
Required fields: system_name, life_event, operating_premise,
                 system_objective, control_domains, key_roles, success_criteria
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


class ControlDomain(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    scope: str = ""


class KeyRole(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str = Field(..., min_length=1)
    responsibility: str = Field(..., min_length=1)


class SystemArchitectureOutput(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    system_name: str = Field(..., min_length=1)
    life_event: str = Field(..., min_length=1)
    operating_premise: str = Field(..., min_length=1)
    system_objective: str = Field(..., min_length=1)
    control_domains: list[ControlDomain] = Field(..., min_length=1)
    key_roles: list[KeyRole] = Field(..., min_length=1)
    success_criteria: list[str] = Field(..., min_length=1)
    operating_constraints: list[str] = []

    @field_validator("success_criteria", mode="before")
    @classmethod
    def _nonempty_strings(cls, v: list) -> list:
        if isinstance(v, list):
            return [str(item) for item in v if item]
        return v
