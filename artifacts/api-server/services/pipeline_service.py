"""
PipelineService — drives stage execution end-to-end.
Coordinates: registry → orchestrator → stage service → validator → storage.
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
from schemas.stage import STAGE_NAMES
from services.llm_client import LLMClient, LLMError
from services.project_service import ProjectService

logger = get_logger(__name__)

orchestrator = PipelineOrchestrator()


def _get_assembler() -> PromptAssembler:
    registry = get_registry()
    orch_contract = registry.resolve("life_system_orchestrator")
    return PromptAssembler(orch_contract)


class PipelineService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._project_svc = ProjectService(db)
        self._llm = LLMClient()

    # ------------------------------------------------------------------ #
    #  Stage output storage helpers                                        #
    # ------------------------------------------------------------------ #

    def get_stage_output(self, project_id: int, stage: str) -> StageOutput | None:
        return (
            self._db.query(StageOutput)
            .filter(
                StageOutput.project_id == project_id,
                StageOutput.stage_name == stage,
            )
            .first()
        )

    def list_stage_outputs(self, project_id: int) -> list[StageOutput]:
        return (
            self._db.query(StageOutput)
            .filter(StageOutput.project_id == project_id)
            .order_by(StageOutput.created_at)
            .all()
        )

    def completed_stages(self, project_id: int) -> set[str]:
        rows = (
            self._db.query(StageOutput.stage_name)
            .filter(
                StageOutput.project_id == project_id,
                StageOutput.status == "complete",
            )
            .all()
        )
        return {row.stage_name for row in rows}

    def all_stage_outputs_as_dict(self, project_id: int) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for row in self.list_stage_outputs(project_id):
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
            existing = self.get_stage_output(project_id, stage)
            if existing:
                logger.info("Stage '%s' already complete for project %d — returning cached", stage, project_id)
                return existing

        orchestrator.check_upstream_complete(stage, completed)

        # Gather context
        all_outputs = self.all_stage_outputs_as_dict(project_id)
        upstream = orchestrator.collect_upstream_outputs(stage, all_outputs)
        payload = {
            "life_event": project.life_event,
            "audience": project.audience or "general adult",
            "tone": project.tone or "professional",
            "context": project.context or "",
        }

        # Resolve contract and assemble prompt
        registry = get_registry()
        contract_name = orchestrator.resolve_contract_name(stage)
        contract = registry.resolve(contract_name)
        assembler = _get_assembler()
        prompt = assembler.assemble(contract, payload, upstream_outputs=upstream)

        # Upsert stage row to "running"
        stage_row = self.get_stage_output(project_id, stage)
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
            self._db.add(stage_row)
        self._db.commit()

        # Call LLM
        try:
            output_json = self._llm.complete(prompt)
            stage_row.set_output(output_json)
            stage_row.status = "complete"
            logger.info("Stage '%s' complete for project %d", stage, project_id)
        except LLMError as e:
            stage_row.status = "failed"
            stage_row.error_message = str(e)
            logger.error("Stage '%s' failed for project %d: %s", stage, project_id, e)
        finally:
            stage_row.updated_at = datetime.now(timezone.utc)
            self._db.commit()
            self._db.refresh(stage_row)

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
