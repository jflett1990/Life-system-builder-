"""
Pydantic schema for the validation_audit stage output.

Contract: v1/life_system_validation_agent.json
Required fields: audit_passed, total_issues, stages_audited, issues,
                 stage_summaries, render_ready, export_ready, audit_summary
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


_SEVERITIES = Literal["error", "warning", "info"]
_ISSUE_CODES = Literal[
    "MISSING_FIELD", "INVALID_REFERENCE", "EMPTY_VALUE",
    "TYPE_MISMATCH", "BROKEN_CROSS_REF"
]
_STAGE_STATUSES = Literal["pass", "fail", "warn"]


class AuditIssue(BaseModel):
    model_config = ConfigDict(extra="allow")

    issue_id: str = Field(..., min_length=1)
    stage: str = Field(..., min_length=1)
    field_path: str = ""
    severity: str = "error"
    code: str = "MISSING_FIELD"
    message: str = Field(..., min_length=1)
    suggested_fix: str = ""


class StageSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    stage: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    issue_count: int = Field(default=0, ge=0)

    @field_validator("issue_count", mode="before")
    @classmethod
    def _coerce_count(cls, v: object) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0


class ValidationAuditOutput(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    audit_passed: bool
    total_issues: int = Field(..., ge=0)
    stages_audited: list[str] = Field(..., min_length=1)
    issues: list[AuditIssue]
    stage_summaries: list[StageSummary] = Field(..., min_length=1)
    render_ready: bool
    export_ready: bool
    audit_summary: str = Field(..., min_length=1)

    @field_validator("total_issues", mode="before")
    @classmethod
    def _coerce_total(cls, v: object) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    @field_validator("audit_passed", "render_ready", "export_ready", mode="before")
    @classmethod
    def _coerce_bool(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)
