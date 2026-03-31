from typing import Any
from pydantic import BaseModel


class RunStageRequest(BaseModel):
    force: bool = False


class ValidationIssue(BaseModel):
    stage: str
    field: str
    severity: str
    message: str


class ValidationReport(BaseModel):
    project_id: int
    passed: bool
    issue_count: int
    issues: list[ValidationIssue]
    summary: str


class PipelineStageSummary(BaseModel):
    stage: str
    status: str
    revision: int


class ProjectSummary(BaseModel):
    project_id: int
    title: str
    life_event: str
    total_stages: int
    completed_stages: int
    stages: list[PipelineStageSummary]
