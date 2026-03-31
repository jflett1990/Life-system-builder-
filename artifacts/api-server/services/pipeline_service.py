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

import json
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
        self._repo.save(stage_row)

        # ── Route to loop or single-call path ─────────────────────────────────
        if contract.execution_mode == "loop_per_chapter":
            self._run_chapter_loop(
                project_id=project_id,
                stage=stage,
                project=project,
                stage_row=stage_row,
                contract=contract,
                all_outputs=all_outputs,
            )
        else:
            assembler = _get_assembler()
            prompt = assembler.assemble(contract, payload, upstream_outputs=upstream)
            self._run_single_call(
                stage=stage,
                project_id=project_id,
                stage_row=stage_row,
                contract=contract,
                prompt=prompt,
            )

        return stage_row

    def _run_single_call(
        self,
        stage: str,
        project_id: int,
        stage_row: Any,
        contract: Any,
        prompt: Any,
    ) -> None:
        """Execute a standard single-LLM-call stage."""
        try:
            structured, parse_result = self._model.generate_structured_output(prompt, contract)

            stage_row.set_raw_output(structured.raw_text)

            if structured.was_repaired:
                logger.warning(
                    "Stage '%s' project %d: JSON required %d repair pass(es)",
                    stage, project_id, structured.repair_attempts,
                )

            if not parse_result.success and parse_result.has_schema:
                stage_row.status = "schema_failed"
                stage_row.error_message = parse_result.for_error_message()
                logger.error(
                    "Stage '%s' SCHEMA FAILED | project=%d | %s",
                    stage, project_id, parse_result.error_summary(5),
                )
            else:
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

                stage_row.set_output(structured.data)
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
            logger.error("Stage '%s' FAILED | project=%d | %s", stage, project_id, str(e)[:300])

        finally:
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)

    def _run_chapter_loop(
        self,
        project_id: int,
        stage: str,
        project: Any,
        stage_row: Any,
        contract: Any,
        all_outputs: dict[str, Any],
    ) -> None:
        """
        Execute the chapter_expansion stage by running one LLM call per chapter
        in the document_outline, then accumulating all results into a single output.

        Each per-chapter call is validated against ExpandedChapter.
        The accumulated output is wrapped in ChapterExpansionOutput.
        Partial failure (some chapters fail) saves what succeeded; total failure
        marks the stage as failed.
        """
        from schemas.stage_outputs.chapter_expansion import ExpandedChapter, ChapterExpansionOutput

        outline_data = all_outputs.get("document_outline", {})
        chapters_plan = outline_data.get("chapters", [])

        if not chapters_plan:
            stage_row.status = "failed"
            stage_row.error_message = "document_outline contains no chapters to expand"
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)
            logger.error("chapter_expansion aborted: document_outline has no chapters")
            return

        # For upstream context injection, the assembler needs system_architecture + document_outline
        upstream = orchestrator.collect_upstream_outputs(stage, all_outputs)
        assembler = _get_assembler()

        base_payload = {
            "life_event": project.life_event,
            "audience": project.audience or "general adult",
            "tone": project.tone or "professional",
            "context": project.context or "",
            "document_title": outline_data.get("document_title", project.life_event),
        }

        expanded_chapters: list[dict] = []
        failed_chapter_numbers: list[int] = []
        raw_texts: list[str] = []

        logger.info(
            "chapter_expansion | project=%d | starting loop over %d chapters",
            project_id, len(chapters_plan),
        )

        for i, chapter_plan in enumerate(chapters_plan):
            chapter_number = chapter_plan.get("chapter_number", i + 1)
            domain_name = chapter_plan.get("domain_name", f"Chapter {chapter_number}")

            logger.info(
                "chapter_expansion | project=%d | chapter %d/%d | domain='%s'",
                project_id, chapter_number, len(chapters_plan), domain_name,
            )

            chapter_payload = {
                **base_payload,
                "current_chapter_json": json.dumps(chapter_plan, indent=2, ensure_ascii=False),
                "chapter_number": str(chapter_number),
                "domain_name": domain_name,
            }

            try:
                prompt = assembler.assemble(contract, chapter_payload, upstream_outputs=upstream)
                structured, parse_result = self._model.generate_structured_output(
                    prompt, contract,
                    schema_class_override=ExpandedChapter,
                )
                raw_texts.append(structured.raw_text)

                if parse_result.success and parse_result.parsed_data:
                    expanded_chapters.append(parse_result.parsed_data)
                    logger.info(
                        "chapter_expansion | chapter %d OK | worksheets=%d",
                        chapter_number,
                        len(parse_result.parsed_data.get("worksheets", [])),
                    )
                else:
                    # Use raw data (schema failed but we have something)
                    expanded_chapters.append(structured.data)
                    logger.warning(
                        "chapter_expansion | chapter %d schema soft-fail — using raw data",
                        chapter_number,
                    )

            except (ModelProviderError, ModelOutputError) as e:
                failed_chapter_numbers.append(chapter_number)
                logger.error(
                    "chapter_expansion | chapter %d FAILED | %s",
                    chapter_number, str(e)[:200],
                )

        # Save all raw model output combined (for debugging)
        stage_row.set_raw_output("\n\n---CHAPTER SEPARATOR---\n\n".join(raw_texts))

        if not expanded_chapters:
            stage_row.status = "failed"
            stage_row.error_message = f"All {len(chapters_plan)} chapters failed to expand"
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)
            logger.error("chapter_expansion | ALL chapters failed | project=%d", project_id)
            return

        # Build accumulated output
        total_worksheets = sum(len(c.get("worksheets", [])) for c in expanded_chapters)
        accumulated = {
            "document_title": outline_data.get("document_title", ""),
            "total_chapters": len(expanded_chapters),
            "total_worksheets": total_worksheets,
            "chapters": expanded_chapters,
        }

        stage_row.set_output(accumulated)
        stage_row.preview_text = (
            f"{len(expanded_chapters)} chapters expanded | "
            f"{total_worksheets} worksheets generated"
            + (f" | {len(failed_chapter_numbers)} chapter(s) failed" if failed_chapter_numbers else "")
        )
        stage_row.status = "complete"

        if failed_chapter_numbers:
            stage_row.error_message = (
                f"Partial expansion: chapters {failed_chapter_numbers} failed — "
                f"{len(expanded_chapters)}/{len(chapters_plan)} succeeded"
            )

        stage_row.updated_at = datetime.now(timezone.utc)
        self._repo.save(stage_row)

        logger.info(
            "chapter_expansion COMPLETE | project=%d | chapters=%d/%d | worksheets=%d",
            project_id, len(expanded_chapters), len(chapters_plan), total_worksheets,
        )

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
