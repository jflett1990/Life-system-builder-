"""
Validation schemas — Pydantic models for API request/response and storage.

These replace the old ValidationIssue / ValidationReport in schemas/pipeline.py.
The old models are kept in pipeline.py for backward compatibility with
existing route references.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


Severity = Literal["fatal", "error", "warning", "info"]
VerdictType = Literal["pass", "fail", "conditional_pass"]


class DefectSchema(BaseModel):
    defect_id:       str
    stage:           str
    rule_id:         str
    severity:        Severity
    code:            str
    title:           str
    field_path:      str
    evidence:        str
    message:         str
    required_fix:    str
    blocked_handoff: bool

    model_config = {"from_attributes": True}


class StageValidationSchema(BaseModel):
    stage:         str
    status:        str    # "pass" | "fail" | "conditional_pass" | "skipped"
    defect_count:  int
    fatal_count:   int
    error_count:   int
    warning_count: int
    info_count:    int    = 0
    defects:       list[DefectSchema]

    model_config = {"from_attributes": True}


class ValidationResultSchema(BaseModel):
    project_id:      int
    verdict:         VerdictType
    blocked_handoff: bool
    total_defects:   int
    fatal_count:     int
    error_count:     int
    warning_count:   int
    info_count:      int    = 0
    summary:         str
    stages:          list[StageValidationSchema]
    defects:         list[DefectSchema]
    skipped_stages:  list[str] = []
    validated_at:    str

    model_config = {"from_attributes": True}

    @classmethod
    def from_engine_result(cls, result: Any) -> "ValidationResultSchema":
        data = result.to_dict()
        return cls(**data)
