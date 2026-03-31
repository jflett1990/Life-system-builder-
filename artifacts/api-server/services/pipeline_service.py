"""
PipelineService — drives stage execution end-to-end.

Execution flow per stage:
  1. Verify stage is known; check upstream stages are complete
  2. Gather project payload + upstream outputs
  3. Resolve contract from registry; assemble prompt
  4. ModelService.generate_structured_output →
       (StructuredOutput, ParseResult)
       - StructuredOutput.data     = schema-validated dict (or raw if no schema / lenient mode)
       - StructuredOutput.raw_text = original model response string
       - ParseResult.parsed_data   = Pydantic-coerced dict
       - ParseResult.success       = did schema validation pass?
       - ParseResult.validation_errors = Pydantic error messages
  5. Persist:
       json_output       = schema-validated dict (what renders / exports)
       raw_model_output  = original model string (for debugging)
  6. ModelService.validate_output → field-presence check (logged, not fatal)
  7. ModelService.generate_preview_text → short summary
  8. Upsert StageOutput row

Error handling:
  - ModelProviderError / ModelOutputError → stage status = "failed"
  - Schema validation fails (strict) → stage status = "schema_failed"
    raw_model_output is always saved BEFORE the schema failure is recorded
    error_message = structured list of Pydantic errors with field paths
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.contract_registry import get_registry
from core.pipeline_orchestrator import PipelineOrchestrator, PipelineError
from core.prompt_assembler import PromptAssembler
from core.logging import get_logger
from models.stage_output import StageOutput
from models_integration import (
    ModelService,
    ModelProviderError,
    ModelOutputError,
)
from repositories.stage_repo import StageOutputRepository
from schemas.stage import STAGE_NAMES
from services.project_service import ProjectService

logger = get_logger(__name__)

orchestrator = PipelineOrchestrator()


def _get_assembler() -> PromptAssembler:
    registry = get_registry()
    orch_contract = registry.resolve("life_system_orchestrator")
    return PromptAssembler(orch_contract)


class PipelineService:
    def __init__(self, db: Session) -> None:
        self._repo = StageOutputRepository(db)
        self._project_svc = ProjectService(db)
        self._model = ModelService(strict_validation=True)

    # ── Read helpers ──────────────────────────────────────────────────────────

    def get_stage_output(self, project_id: int, stage: str) -> StageOutput | None:
        return self._repo.find_by_project_and_stage(project_id, stage)

    def list_stage_outputs(self, project_id: int) -> list[StageOutput]:
        return self._repo.find_all_for_project(project_id)

    def completed_stages(self, project_id: int) -> set[str]:
        return self._repo.find_completed_stage_names(project_id)

    def all_stage_outputs_as_dict(self, project_id: int) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for row in self._repo.find_all_for_project(project_id):
            if row.status == "complete" and row.json_output:
                outputs[row.stage_name] = row.get_output()
        return outputs

    # ── Stage execution ───────────────────────────────────────────────────────

    def run_stage(
        self, project_id: int, stage: str, force: bool = False
    ) -> StageOutput:
        if stage not in STAGE_NAMES:
            raise PipelineError(f"Unknown stage '{stage}'. Valid: {STAGE_NAMES}")

        project = self._project_svc.get(project_id)
        completed = self.completed_stages(project_id)

        if stage in completed and not force:
            existing = self._repo.find_by_project_and_stage(project_id, stage)
            if existing:
                logger.info(
                    "Stage '%s' already complete for project %d — returning cached",
                    stage, project_id,
                )
                return existing

        orchestrator.check_upstream_complete(stage, completed)

        # Assemble context
        all_outputs = self.all_stage_outputs_as_dict(project_id)
        upstream = orchestrator.collect_upstream_outputs(stage, all_outputs)
        payload = {
            "life_event": project.life_event,
            "audience": project.audience or "general adult",
            "tone": project.tone or "professional",
            "context": project.context or "",
        }

        registry = get_registry()
        contract_name = orchestrator.resolve_contract_name(stage)
        contract = registry.resolve(contract_name)
        assembler = _get_assembler()
        prompt = assembler.assemble(contract, payload, upstream_outputs=upstream)

        # Upsert stage row → "running"
        stage_row = self._repo.find_by_project_and_stage(project_id, stage)
        if stage_row:
            stage_row.status = "running"
            stage_row.error_message = None
            stage_row.revision_number += 1
            stage_row.updated_at = datetime.now(timezone.utc)
        else:
            stage_row = StageOutput(
                project_id=project_id,
                stage_name=stage,
                status="running",
                revision_number=1,
            )
            self._repo.insert(stage_row)

        # ── Run model pipeline ────────────────────────────────────────────────
        try:
            structured, parse_result = self._model.generate_structured_output(prompt, contract)

            # Always persist raw model output immediately — before any further processing
            # that might raise so we never lose the LLM response on schema failure.
            stage_row.set_raw_output(structured.raw_text)

            if structured.was_repaired:
                logger.warning(
                    "Stage '%s' project %d: JSON required %d repair pass(es)",
                    stage, project_id, structured.repair_attempts,
                )

            # If schema validation failed, mark as schema_failed now that raw text is saved
            if not parse_result.success and parse_result.has_schema:
                stage_row.status = "schema_failed"
                stage_row.error_message = parse_result.for_error_message()
                logger.error(
                    "Stage '%s' SCHEMA FAILED | project=%d | %s",
                    stage, project_id, parse_result.error_summary(5),
                )
            else:
                # Log structural field-presence validation (non-fatal)
                field_validation = self._model.validate_output(
                    stage=stage,
                    output=structured.data,
                    required_fields=contract.required_output_fields,
                    schema=contract.output_schema,
                )
                if not field_validation.valid:
                    logger.warning(
                        "Stage '%s' project %d field validation: %s",
                        stage, project_id, field_validation.error_summary,
                    )
                    stage_row.set_validation(field_validation.to_dict())

                # Persist the validated (or best-available) output dict
                stage_row.set_output(structured.data)

                # Generate and store preview text
                preview = self._model.generate_preview_text(stage, structured.data)
                stage_row.preview_text = preview.text

                stage_row.status = "complete"

                logger.info(
                    "Stage '%s' COMPLETE | project=%d | schema_pass=%s | repaired=%s "
                    "| attempt=%d | preview_from_llm=%s",
                    stage, project_id,
                    parse_result.success,
                    structured.was_repaired,
                    parse_result.attempt,
                    preview.from_llm,
                )

        except (ModelProviderError, ModelOutputError) as e:
            stage_row.status = "failed"
            stage_row.error_message = str(e)
            logger.error(
                "Stage '%s' FAILED | project=%d | %s",
                stage, project_id, str(e)[:300],
            )

        finally:
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)

        return stage_row

    def run_full_pipeline(self, project_id: int) -> list[StageOutput]:
        results: list[StageOutput] = []
        for stage in STAGE_NAMES:
            result = self.run_stage(project_id, stage)
            results.append(result)
            if result.status in ("failed", "schema_failed"):
                logger.warning(
                    "Pipeline halted at stage '%s' (status=%s)", stage, result.status
                )
                break
        return results
