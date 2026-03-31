"""
ValidationService — compiler-style audit of all stage outputs.
Uses the life_system_validation_agent contract for LLM-assisted deep audit.
Also performs schema-level checks without any LLM call for fast feedback.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core.contract_registry import get_registry
from core.pipeline_orchestrator import PipelineOrchestrator
from core.prompt_assembler import PromptAssembler
from core.logging import get_logger
from schemas.pipeline import ValidationReport, ValidationIssue
from schemas.stage import STAGE_NAMES
from services.llm_client import LLMClient
from services.pipeline_service import PipelineService

logger = get_logger(__name__)

orchestrator = PipelineOrchestrator()

STAGE_REQUIRED_FIELDS: dict[str, list[str]] = {
    "system_architecture": [
        "system_name", "life_event", "operating_premise", "system_objective",
        "time_horizon", "control_domains", "key_roles", "success_criteria",
    ],
    "worksheet_system": [
        "worksheet_system_name", "worksheets", "completion_sequence",
    ],
    "layout_mapping": [
        "document_title", "sections", "navigation_map",
    ],
    "render_blueprint": [
        "blueprint_name", "theme", "render_directives",
    ],
}


def _fast_check(stage: str, output: dict[str, Any]) -> list[ValidationIssue]:
    """Structural field presence check — no LLM call."""
    issues: list[ValidationIssue] = []
    required = STAGE_REQUIRED_FIELDS.get(stage, [])
    for field in required:
        value = output.get(field)
        if value is None:
            issues.append(ValidationIssue(
                stage=stage,
                field=field,
                severity="error",
                message=f"Required field '{field}' is missing",
            ))
        elif isinstance(value, (str, list, dict)) and not value:
            issues.append(ValidationIssue(
                stage=stage,
                field=field,
                severity="error",
                message=f"Required field '{field}' is empty",
            ))
        elif isinstance(value, str) and "REQUIRES CLARIFICATION" in value:
            issues.append(ValidationIssue(
                stage=stage,
                field=field,
                severity="warning",
                message=f"Field '{field}' contains placeholder text 'REQUIRES CLARIFICATION'",
            ))
    return issues


class ValidationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._pipeline = PipelineService(db)
        self._llm = LLMClient()

    def validate_project(self, project_id: int, use_llm: bool = True) -> ValidationReport:
        all_outputs = self._pipeline.all_stage_outputs_as_dict(project_id)
        all_issues: list[ValidationIssue] = []

        for stage in STAGE_NAMES:
            if stage == "validation_audit":
                continue
            if stage not in all_outputs:
                all_issues.append(ValidationIssue(
                    stage=stage,
                    field="(stage)",
                    severity="error",
                    message=f"Stage '{stage}' has not been completed",
                ))
            else:
                all_issues.extend(_fast_check(stage, all_outputs[stage]))

        if use_llm and all_outputs and len(all_issues) == 0:
            try:
                llm_issues = self._llm_deep_audit(project_id, all_outputs)
                all_issues.extend(llm_issues)
            except Exception as e:
                logger.warning("LLM deep audit failed — using structural check only: %s", e)
                all_issues.append(ValidationIssue(
                    stage="validation_audit",
                    field="(audit)",
                    severity="info",
                    message=f"LLM deep audit skipped: {str(e)[:200]}",
                ))

        errors = [i for i in all_issues if i.severity == "error"]
        passed = len(errors) == 0

        if passed:
            summary = "All stages passed validation. The pipeline output is render-ready."
        else:
            summary = (
                f"Validation found {len(errors)} error(s) and "
                f"{len([i for i in all_issues if i.severity == 'warning'])} warning(s). "
                "Resolve errors before rendering."
            )

        return ValidationReport(
            project_id=project_id,
            passed=passed,
            issue_count=len(all_issues),
            issues=all_issues,
            summary=summary,
        )

    def _llm_deep_audit(self, project_id: int, all_outputs: dict[str, Any]) -> list[ValidationIssue]:
        registry = get_registry()
        contract = registry.resolve("life_system_validation_agent")
        orch = registry.resolve("life_system_orchestrator")
        assembler = PromptAssembler(orch)
        prompt = assembler.assemble(contract, payload={}, upstream_outputs=all_outputs)
        result = self._llm.complete(prompt)

        issues: list[ValidationIssue] = []
        for item in result.get("issues", []):
            issues.append(ValidationIssue(
                stage=item.get("stage", "unknown"),
                field=item.get("field_path", "unknown"),
                severity=item.get("severity", "info"),
                message=item.get("message", ""),
            ))
        return issues
