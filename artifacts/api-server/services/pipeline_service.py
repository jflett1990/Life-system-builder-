"""
PipelineService — drives stage execution end-to-end.

Model calls go through ModelService only — no LLMClient imports here.

Flow per stage:
  1. Verify stage is known and upstream stages are complete
  2. Gather upstream outputs + project payload
  3. Resolve contract from registry
  4. Assemble prompt via PromptAssembler
  5. Call ModelService.generate_structured_output → StructuredOutput
  6. Run ModelService.validate_output — log warnings, record in stage row
  7. Call ModelService.generate_preview_text → preview string
  8. Persist StageOutput (upsert via StageOutputRepository)
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
    OutputValidationError,
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
        self._model = ModelService(strict_validation=False)

    # ------------------------------------------------------------------ #
    #  Read helpers                                                        #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    #  Stage execution                                                     #
    # ------------------------------------------------------------------ #

    def run_stage(self, project_id: int, stage: str, force: bool = False) -> StageOutput:
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

        # Run model pipeline
        try:
            structured = self._model.generate_structured_output(prompt, contract)

            # Store validation result as metadata on the stage row
            validation = self._model.validate_output(
                stage=stage,
                output=structured.data,
                required_fields=contract.required_output_fields,
                schema=contract.output_schema,
            )
            if not validation.valid:
                logger.warning(
                    "Stage '%s' project %d: %s",
                    stage, project_id, validation.error_summary,
                )
                stage_row.set_validation(validation.to_dict())

            # Generate preview text
            preview = self._model.generate_preview_text(stage, structured.data)
            stage_row.preview_text = preview.text

            stage_row.set_output(structured.data)
            stage_row.status = "complete"

            logger.info(
                "Stage '%s' complete for project %d | repaired=%s | preview_from_llm=%s",
                stage, project_id, structured.was_repaired, preview.from_llm,
            )

        except (ModelProviderError, ModelOutputError, OutputValidationError) as e:
            stage_row.status = "failed"
            stage_row.error_message = str(e)
            logger.error("Stage '%s' failed for project %d: %s", stage, project_id, e)

        finally:
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)

        return stage_row

    def run_full_pipeline(self, project_id: int) -> list[StageOutput]:
        results: list[StageOutput] = []
        for stage in STAGE_NAMES:
            result = self.run_stage(project_id, stage)
            results.append(result)
            if result.status == "failed":
                logger.warning("Pipeline halted at stage '%s' due to failure", stage)
                break
        return results
