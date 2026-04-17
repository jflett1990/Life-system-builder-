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
import concurrent.futures
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.config import settings
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
from schemas.stage import STAGE_NAMES, ALL_STAGE_NAMES
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
        if stage not in ALL_STAGE_NAMES:
            raise PipelineError(f"Unknown stage '{stage}'. Valid: {ALL_STAGE_NAMES}")

        # v2 stages have dedicated handlers that bypass the standard LLM contract flow
        if stage == "research_graph":
            return self._run_research_graph_stage(project_id, force=force)
        if stage == "content_plan":
            return self._run_content_plan_stage(project_id, force=force)
        if stage == "voice_profile":
            return self._run_voice_profile_stage(project_id, force=force)

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
            if stage == "chapter_worksheets":
                self._run_chapter_worksheets_loop(
                    project_id=project_id,
                    stage=stage,
                    project=project,
                    stage_row=stage_row,
                    contract=contract,
                    all_outputs=all_outputs,
                )
            else:
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
        Execute the chapter_expansion stage as a TWO-PASS process per chapter,
        running up to 4 chapters concurrently.

        Pass 1 — chapter_narrative_writer contract:
            A dedicated LLM call that writes ONLY the operational narrative for
            one chapter (target 3500–5000 words).  No competing output fields.

        Pass 2 — chapter_expansion contract (structure pass):
            A second LLM call that receives the narrative from Pass 1 and
            generates the structural elements: quick_reference_rules,
            cascade_triggers, scenario_scene, and success_metrics.

        The results of both passes are merged into a single chapter dict and
        accumulated in chapter_number order.  Worksheets are not generated here —
        that is the responsibility of the separate chapter_worksheets stage.

        Partial failure (some chapters fail) saves what succeeded; total failure
        marks the stage as failed.  Progress is written to stage_row.sub_progress
        after each chapter completes so the frontend can show live status.
        """
        from schemas.stage_outputs.chapter_expansion import (
            ChapterNarrativeOutput,
            ChapterExpansionStructure,
            ChapterExpansionOutput,
        )

        outline_data = all_outputs.get("document_outline", {})
        chapters_plan = outline_data.get("chapters", [])

        if not chapters_plan:
            stage_row.status = "failed"
            stage_row.error_message = "document_outline contains no chapters to expand"
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)
            logger.error("chapter_expansion aborted: document_outline has no chapters")
            return

        # Phase C: load voice profile for genericity guard (optional — no-op if absent)
        voice_profile_output = all_outputs.get("voice_profile", {})

        # For upstream context injection, the assembler needs system_architecture + document_outline
        upstream = orchestrator.collect_upstream_outputs(stage, all_outputs)
        assembler = _get_assembler()

        # Load the narrative sub-call contract (Pass 1)
        narrative_contract = get_registry().resolve("chapter_narrative_writer")

        base_payload = {
            "life_event": project.life_event,
            "audience": project.audience or "general adult",
            "tone": project.tone or "professional",
            "context": project.context or "",
            "document_title": outline_data.get("document_title", project.life_event),
        }

        total = len(chapters_plan)

        logger.info(
            "chapter_expansion | project=%d | starting 2-pass parallel loop over %d chapters "
            "(pass 1: narrative, pass 2: structure) max_workers=4",
            project_id, total,
        )

        # Phase C: instantiate genericity guard once per stage run (shared across chapters)
        from authoring.genericity_guard import GenericityGuard
        _guard = GenericityGuard(project_id=project_id, voice_profile=voice_profile_output)

        # ── Per-chapter worker (pure, no DB access, thread-safe) ────────────────
        def _expand_one(chapter_plan: dict, idx: int) -> tuple[int, str, dict | None, str]:
            """
            Run two sequential LLM sub-calls for one chapter and return the merged result.

            Returns (chapter_number, domain_name, merged_chapter_dict_or_None, combined_raw_text).
            merged_chapter_dict is None on total failure.
            """
            chapter_number = chapter_plan.get("chapter_number", idx + 1)
            domain_name = chapter_plan.get("domain_name", f"Chapter {chapter_number}")

            chapter_payload = {
                **base_payload,
                "current_chapter_json": json.dumps(chapter_plan, indent=2, ensure_ascii=False),
                "chapter_number": int(chapter_number),
                "domain_name": domain_name,
            }

            try:
                # ── Pass 1: Deep narrative with UX-layer enforcement ───────────────
                narrative = ""
                narrative_raw_parts: list[str] = []
                narrative_fix_instructions = ""
                for narrative_attempt in range(2):
                    narrative_payload = {
                        **chapter_payload,
                        "narrative_fix_instructions": narrative_fix_instructions,
                    }
                    narrative_prompt = assembler.assemble(
                        narrative_contract, narrative_payload, upstream_outputs=upstream
                    )
                    narrative_structured, narrative_parse = self._model.generate_structured_output(
                        narrative_prompt, narrative_contract,
                        schema_class_override=ChapterNarrativeOutput,
                    )
                    narrative_raw_parts.append(narrative_structured.raw_text)

                    if narrative_parse.success and narrative_parse.parsed_data:
                        narrative = narrative_parse.parsed_data.get("narrative", "")
                    elif narrative_structured.data:
                        narrative = narrative_structured.data.get("narrative", "")

                    narrative_defects = self._chapter_narrative_defects(narrative)
                    if not narrative_defects:
                        break
                    narrative_fix_instructions = (
                        "Previous draft failed narrative layering checks. Fix ALL items:\n- "
                        + "\n- ".join(narrative_defects)
                    )
                    logger.warning(
                        "chapter_expansion | chapter %d | narrative repair pass required: %s",
                        chapter_number, "; ".join(narrative_defects),
                    )

                if not narrative:
                    logger.error(
                        "chapter_expansion | chapter %d | Pass 1 (narrative) returned empty — "
                        "aborting chapter",
                        chapter_number,
                    )
                    return chapter_number, domain_name, None, "\n\n".join(narrative_raw_parts)

                logger.info(
                    "chapter_expansion | chapter %d | Pass 1 complete | ~%d words",
                    chapter_number, len(narrative.split()),
                )

                # ── Phase C: Genericity guard on Pass 1 narrative (retry budget=2) ──
                guard_result, should_retry = _guard.check_with_retry_budget(narrative, max_retries=2)
                if not guard_result.passed and should_retry:
                    logger.info(
                        "chapter_expansion | chapter %d | genericity guard FAIL — "
                        "injecting retry context into Pass 2",
                        chapter_number,
                    )
                    # Inject guard rejection context into the structure pass payload
                    narrative_fix_instructions = guard_result.retry_context

                # ── Pass 2: Structure (quick_reference_rules, cascade_triggers, scenario, metrics)
                # Inject the narrative so every structural element is grounded in the chapter content.
                merged: dict[str, Any] = {}
                structure_raw_parts: list[str] = []
                structure_fix_instructions = ""
                for structure_attempt in range(2):
                    chapter_payload_with_narrative = {
                        **chapter_payload,
                        "chapter_narrative": narrative,
                        "structure_fix_instructions": structure_fix_instructions,
                    }

                    structure_prompt = assembler.assemble(
                        contract, chapter_payload_with_narrative, upstream_outputs=upstream
                    )
                    structure_structured, structure_parse = self._model.generate_structured_output(
                        structure_prompt, contract,
                        schema_class_override=ChapterExpansionStructure,
                    )
                    structure_raw_parts.append(structure_structured.raw_text)

                    if structure_parse.success and structure_parse.parsed_data:
                        merged = dict(structure_parse.parsed_data)
                    else:
                        merged = dict(structure_structured.data or {})

                    structure_defects = self._chapter_structure_defects(merged)
                    if not structure_defects:
                        break
                    structure_fix_instructions = (
                        "Previous draft failed required chapter schema. Fix ALL items:\n- "
                        + "\n- ".join(structure_defects)
                    )
                    logger.warning(
                        "chapter_expansion | chapter %d | structure repair pass required: %s",
                        chapter_number, "; ".join(structure_defects),
                    )

                # Inject the narrative from Pass 1 into the merged output.
                # Ensure required top-level fields are present even if Pass 2 omitted them.
                merged["narrative"] = narrative
                merged.setdefault("detailed_explanation", narrative)
                merged.setdefault("chapter_number", chapter_number)
                merged.setdefault(
                    "chapter_title",
                    chapter_plan.get("chapter_title", f"Chapter {chapter_number}"),
                )
                merged.setdefault("domain_id", chapter_plan.get("domain_id", ""))
                # worksheets field kept for backwards compat — populated by chapter_worksheets stage
                merged.setdefault("worksheets", [])
                final_defects = self._chapter_structure_defects(merged)
                if final_defects:
                    logger.error(
                        "chapter_expansion | chapter %d FAILED contract enforcement: %s",
                        chapter_number, "; ".join(final_defects),
                    )
                    return chapter_number, domain_name, None, "\n\n".join(narrative_raw_parts + structure_raw_parts)

                combined_raw = (
                    "\n\n---NARRATIVE/STRUCTURE SEPARATOR---\n\n".join(
                        [*narrative_raw_parts, *structure_raw_parts]
                    )
                )

                logger.info(
                    "chapter_expansion | chapter %d complete | ~%d words | "
                    "rules=%d | triggers=%d | metrics=%d",
                    chapter_number,
                    len(narrative.split()),
                    len(merged.get("quick_reference_rules", [])),
                    len(merged.get("cascade_triggers", [])),
                    len(merged.get("success_metrics", [])),
                )
                return chapter_number, domain_name, merged, combined_raw

            except Exception as e:
                logger.error(
                    "chapter_expansion | chapter %d FAILED | %s",
                    chapter_number, str(e)[:200],
                )
                return chapter_number, domain_name, None, ""

        # ── Collect results keyed by chapter_number ──────────────────────────
        # We keep (chapter_number, data) tuples so we can re-sort to document order.
        results_by_number: dict[int, dict] = {}
        failed_chapter_numbers: list[int] = []
        raw_texts_by_number: dict[int, str] = {}
        completed_count = 0

        _WORKERS = settings.chapter_expansion_workers

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=_WORKERS, thread_name_prefix="chapter-worker"
        ) as pool:
            # Build future → chapter info mapping so we can derive current_domains
            future_to_chapter: dict[concurrent.futures.Future, dict] = {
                pool.submit(_expand_one, chap, i): chap
                for i, chap in enumerate(chapters_plan)
            }

            # All pending futures = all submitted (pool drains them as workers free up)
            pending_futures: set[concurrent.futures.Future] = set(future_to_chapter.keys())

            def _current_domains() -> list[str]:
                """Names of chapters whose worker thread is actively executing.

                Uses Future.running() to distinguish threads that have started from
                those still queued in the executor. Falls back to all pending when
                nothing is marked running yet (e.g. first tick before workers start).
                """
                running = [
                    future_to_chapter[f].get(
                        "domain_name",
                        f"Chapter {future_to_chapter[f].get('chapter_number', '?')}"
                    )
                    for f in pending_futures
                    if f.running()
                ]
                if running:
                    return running[:_WORKERS]
                # Fallback: nothing marked running yet — show first N pending
                return [
                    future_to_chapter[f].get(
                        "domain_name",
                        f"Chapter {future_to_chapter[f].get('chapter_number', '?')}"
                    )
                    for f in list(pending_futures)[:_WORKERS]
                ]

            # Initialise sub_progress so the frontend sees it immediately
            stage_row.set_sub_progress({
                "completed": 0,
                "total": total,
                "current_domains": _current_domains(),
            })
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)

            for future in concurrent.futures.as_completed(future_to_chapter):
                chapter_number, domain_name, chapter_data, raw_text = future.result()
                completed_count += 1
                pending_futures.discard(future)

                if chapter_data is not None:
                    results_by_number[chapter_number] = chapter_data
                    raw_texts_by_number[chapter_number] = raw_text
                else:
                    failed_chapter_numbers.append(chapter_number)

                # Write incremental progress to DB on the main thread
                stage_row.set_sub_progress({
                    "completed": completed_count,
                    "total": total,
                    "current_domains": _current_domains(),
                })
                stage_row.updated_at = datetime.now(timezone.utc)
                self._repo.save(stage_row)

                logger.info(
                    "chapter_expansion | project=%d | %d/%d complete | domain='%s' | in_flight=%d",
                    project_id, completed_count, total, domain_name, len(pending_futures),
                )

        # ── Rebuild chapter list in original document order ──────────────────
        expanded_chapters: list[dict] = []
        raw_texts: list[str] = []
        for chap in chapters_plan:
            cn = chap.get("chapter_number", 0)
            if cn in results_by_number:
                expanded_chapters.append(results_by_number[cn])
                raw_texts.append(raw_texts_by_number.get(cn, ""))

        # Save all raw model output combined (for debugging)
        stage_row.set_raw_output("\n\n---CHAPTER SEPARATOR---\n\n".join(raw_texts))

        if not expanded_chapters:
            stage_row.status = "failed"
            stage_row.error_message = f"All {len(chapters_plan)} chapters failed to expand"
            stage_row.sub_progress = None
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

        # Estimate total narrative word count across all expanded chapters
        total_words = sum(
            len(c.get("narrative", "").split()) for c in expanded_chapters
        )
        stage_row.preview_text = (
            f"{len(expanded_chapters)} chapters expanded | "
            f"~{total_words:,} words of narrative generated"
            + (f" | {len(failed_chapter_numbers)} chapter(s) failed" if failed_chapter_numbers else "")
        )
        stage_row.status = "complete"
        stage_row.sub_progress = None  # clear progress indicator on completion

        if failed_chapter_numbers:
            stage_row.error_message = (
                f"Partial expansion: chapters {sorted(failed_chapter_numbers)} failed — "
                f"{len(expanded_chapters)}/{len(chapters_plan)} succeeded"
            )

        stage_row.updated_at = datetime.now(timezone.utc)
        self._repo.save(stage_row)

        logger.info(
            "chapter_expansion COMPLETE | project=%d | chapters=%d/%d | ~%d total words",
            project_id, len(expanded_chapters), len(chapters_plan), total_words,
        )

    @staticmethod
    def _chapter_narrative_defects(narrative: str) -> list[str]:
        defects: list[str] = []
        required_headings = [
            "## Orientation Snapshot",
            "## Immediate Execution Path",
            "## Deep Operational Guidance",
            "## Failure Dynamics and Recovery",
            "## Cross-Domain Handoffs",
        ]
        for heading in required_headings:
            if heading not in narrative:
                defects.append(f"Missing heading: {heading}")

        paragraphs = [p.strip() for p in re.split(r"\n{2,}", narrative) if p.strip() and not p.strip().startswith("## ")]
        oversized = [p for p in paragraphs if len(p.split()) > 140]
        if oversized:
            defects.append(f"{len(oversized)} paragraph(s) exceed 140 words")
        return defects

    @staticmethod
    def _chapter_structure_defects(chapter: dict[str, Any]) -> list[str]:
        defects: list[str] = []
        opener = chapter.get("chapter_opener") or {}
        required_opener = ("what_this_is_for", "when_it_matters", "failure_looks_like", "produces", "do_first")
        for key in required_opener:
            if not opener.get(key):
                defects.append(f"chapter_opener.{key} is required")

        if len(chapter.get("minimum_viable_actions") or []) < 3:
            defects.append("minimum_viable_actions must contain at least 3 items")
        if len(chapter.get("decision_guide") or []) < 3:
            defects.append("decision_guide must contain at least 3 decisions")
        if len(chapter.get("trigger_blocks") or []) < 2:
            defects.append("trigger_blocks must contain at least 2 items")
        if len(chapter.get("risk_blocks") or []) < 2:
            defects.append("risk_blocks must contain at least 2 items")
        if len(chapter.get("output_summaries") or []) < 2:
            defects.append("output_summaries must contain at least 2 items")
        if not (chapter.get("worksheet_linkage") or []):
            defects.append("worksheet_linkage must contain at least 1 item")
        if not (chapter.get("detailed_explanation") or "").strip():
            defects.append("detailed_explanation is required")
        return defects

    def _run_chapter_worksheets_loop(
        self,
        project_id: int,
        stage: str,
        project: Any,
        stage_row: Any,
        contract: Any,
        all_outputs: dict[str, Any],
    ) -> None:
        """
        Execute the chapter_worksheets stage by running one LLM call per chapter
        concurrently (up to 4 at once), then accumulating results in chapter_number order.

        Each call receives the chapter plan from document_outline plus the narrative
        from chapter_expansion, so worksheets are built with full content context.

        Progress is written to stage_row.sub_progress after each chapter completes.
        """
        from schemas.stage_outputs.chapter_worksheets import ChapterWorksheetsOutput

        outline_data = all_outputs.get("document_outline", {})
        chapters_plan = outline_data.get("chapters", [])

        if not chapters_plan:
            stage_row.status = "failed"
            stage_row.error_message = "document_outline contains no chapters to generate worksheets for"
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)
            logger.error("chapter_worksheets aborted: document_outline has no chapters")
            return

        # Build narrative lookup from chapter_expansion output
        chapter_expansion = all_outputs.get("chapter_expansion", {})
        narrative_by_number: dict[int, str] = {}
        for ch in chapter_expansion.get("chapters", []):
            cn = ch.get("chapter_number", 0)
            narrative_by_number[cn] = ch.get("narrative", "")

        upstream = orchestrator.collect_upstream_outputs(stage, all_outputs)
        assembler = _get_assembler()

        base_payload = {
            "life_event": project.life_event,
            "audience": project.audience or "general adult",
            "tone": project.tone or "professional",
            "context": project.context or "",
            "document_title": outline_data.get("document_title", project.life_event),
        }

        total = len(chapters_plan)

        logger.info(
            "chapter_worksheets | project=%d | starting parallel loop over %d chapters (max_workers=4)",
            project_id, total,
        )

        # ── Per-chapter worker ────────────────────────────────────────────────
        def _generate_worksheets(chapter_plan: dict, idx: int) -> tuple[int, str, dict | None, str]:
            chapter_number = chapter_plan.get("chapter_number", idx + 1)
            domain_name = chapter_plan.get("domain_name", f"Chapter {chapter_number}")
            narrative = narrative_by_number.get(chapter_number, "")

            chapter_payload = {
                **base_payload,
                "current_chapter_json": json.dumps(chapter_plan, indent=2, ensure_ascii=False),
                "chapter_narrative": narrative,
                "chapter_number": int(chapter_number),
                "domain_name": domain_name,
            }

            try:
                prompt = assembler.assemble(contract, chapter_payload, upstream_outputs=upstream)
                structured, parse_result = self._model.generate_structured_output(
                    prompt, contract,
                    schema_class_override=ChapterWorksheetsOutput,
                )
                raw = structured.raw_text

                if parse_result.success and parse_result.parsed_data:
                    logger.info(
                        "chapter_worksheets | chapter %d OK | worksheets=%d",
                        chapter_number,
                        len(parse_result.parsed_data.get("worksheets", [])),
                    )
                    return chapter_number, domain_name, parse_result.parsed_data, raw
                else:
                    logger.warning(
                        "chapter_worksheets | chapter %d schema soft-fail — using raw data",
                        chapter_number,
                    )
                    return chapter_number, domain_name, structured.data, raw

            except Exception as e:
                logger.error(
                    "chapter_worksheets | chapter %d FAILED | %s",
                    chapter_number, str(e)[:200],
                )
                return chapter_number, domain_name, None, ""

        # ── Collect results ───────────────────────────────────────────────────
        results_by_number: dict[int, dict] = {}
        failed_chapter_numbers: list[int] = []
        raw_texts_by_number: dict[int, str] = {}
        completed_count = 0

        _WORKERS = 4

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=_WORKERS, thread_name_prefix="ws-worker"
        ) as pool:
            future_to_chapter: dict[concurrent.futures.Future, dict] = {
                pool.submit(_generate_worksheets, chap, i): chap
                for i, chap in enumerate(chapters_plan)
            }
            pending_futures: set[concurrent.futures.Future] = set(future_to_chapter.keys())

            def _current_domains() -> list[str]:
                running = [
                    future_to_chapter[f].get(
                        "domain_name",
                        f"Chapter {future_to_chapter[f].get('chapter_number', '?')}"
                    )
                    for f in pending_futures
                    if f.running()
                ]
                if running:
                    return running[:_WORKERS]
                return [
                    future_to_chapter[f].get(
                        "domain_name",
                        f"Chapter {future_to_chapter[f].get('chapter_number', '?')}"
                    )
                    for f in list(pending_futures)[:_WORKERS]
                ]

            stage_row.set_sub_progress({
                "completed": 0,
                "total": total,
                "current_domains": _current_domains(),
            })
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)

            for future in concurrent.futures.as_completed(future_to_chapter):
                chapter_number, domain_name, chapter_data, raw_text = future.result()
                completed_count += 1
                pending_futures.discard(future)

                if chapter_data is not None:
                    results_by_number[chapter_number] = chapter_data
                    raw_texts_by_number[chapter_number] = raw_text
                else:
                    failed_chapter_numbers.append(chapter_number)

                stage_row.set_sub_progress({
                    "completed": completed_count,
                    "total": total,
                    "current_domains": _current_domains(),
                })
                stage_row.updated_at = datetime.now(timezone.utc)
                self._repo.save(stage_row)

                logger.info(
                    "chapter_worksheets | project=%d | %d/%d complete | domain='%s' | in_flight=%d",
                    project_id, completed_count, total, domain_name, len(pending_futures),
                )

        # ── Rebuild in document order ─────────────────────────────────────────
        chapter_results: list[dict] = []
        raw_texts: list[str] = []
        for chap in chapters_plan:
            cn = chap.get("chapter_number", 0)
            if cn in results_by_number:
                chapter_results.append(results_by_number[cn])
                raw_texts.append(raw_texts_by_number.get(cn, ""))

        stage_row.set_raw_output("\n\n---CHAPTER SEPARATOR---\n\n".join(raw_texts))

        if not chapter_results:
            stage_row.status = "failed"
            stage_row.error_message = f"All {len(chapters_plan)} chapters failed worksheet generation"
            stage_row.sub_progress = None
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)
            logger.error("chapter_worksheets | ALL chapters failed | project=%d", project_id)
            return

        total_worksheets = sum(len(c.get("worksheets", [])) for c in chapter_results)
        accumulated = {
            "total_chapters": len(chapter_results),
            "total_worksheets": total_worksheets,
            "chapters": chapter_results,
        }

        stage_row.set_output(accumulated)
        stage_row.preview_text = (
            f"{len(chapter_results)} chapters | {total_worksheets} worksheets generated"
            + (f" | {len(failed_chapter_numbers)} chapter(s) failed" if failed_chapter_numbers else "")
        )
        stage_row.status = "complete"
        stage_row.sub_progress = None

        if failed_chapter_numbers:
            stage_row.error_message = (
                f"Partial: chapters {sorted(failed_chapter_numbers)} failed — "
                f"{len(chapter_results)}/{len(chapters_plan)} succeeded"
            )

        stage_row.updated_at = datetime.now(timezone.utc)
        self._repo.save(stage_row)

        logger.info(
            "chapter_worksheets COMPLETE | project=%d | chapters=%d/%d | worksheets=%d",
            project_id, len(chapter_results), len(chapters_plan), total_worksheets,
        )

    # ── v2 stage handlers ──────────────────────────────────────────────────────

    def _make_v2_stage_row(
        self,
        project_id: int,
        stage: str,
        force: bool,
    ) -> StageOutput | None:
        """Upsert a stage row to 'running'. Returns None if stage is cached and force=False."""
        completed = self.completed_stages(project_id)
        if stage in completed and not force:
            existing = self._repo.find_by_project_and_stage(project_id, stage)
            if existing:
                logger.info("Stage '%s' already complete for project %d — returning cached", stage, project_id)
                return existing

        orchestrator.check_upstream_complete(stage, completed)
        row = self._repo.find_by_project_and_stage(project_id, stage)
        if row:
            row.status = "running"
            row.error_message = None
            row.revision_number += 1
            row.updated_at = datetime.now(timezone.utc)
        else:
            row = StageOutput(project_id=project_id, stage_name=stage, status="running", revision_number=1)
            self._repo.insert(row)
        self._repo.save(row)
        return row

    def _run_research_graph_stage(self, project_id: int, *, force: bool = False) -> StageOutput:
        """Stage 1 — Research Graph: deterministic retrieval + fact extraction."""
        from research.graph_builder import build_research_graph

        stage_row = self._make_v2_stage_row(project_id, "research_graph", force)
        if stage_row and stage_row.status == "complete":
            return stage_row

        project = self._project_svc.get(project_id)
        all_outputs = self.all_stage_outputs_as_dict(project_id)
        arch = all_outputs.get("system_architecture", {})

        brief = {
            "life_event_type": project.life_event or arch.get("life_event", ""),
            "life_event":      project.life_event or arch.get("life_event", ""),
            "people":          arch.get("key_roles", []),
            "systems":         [d.get("name", "") for d in arch.get("control_domains", [])],
            "jurisdiction":    project.context or None,
            "jurisdiction_tags": [],
        }

        try:
            graph, followup_questions = build_research_graph(project_id, brief)
            output = {
                **graph.model_dump(),
                "followup_questions": followup_questions,
            }
            stage_row.set_output(output)
            stage_row.preview_text = (
                f"{graph.total_facts} facts | coverage={'PASS' if graph.critical_coverage_met else 'FAIL'} "
                f"| conflicts={graph.conflict_count} | low_conf={graph.low_confidence_count}"
            )
            stage_row.status = "complete"
            logger.info(
                "research_graph COMPLETE | project=%d | facts=%d | coverage_met=%s",
                project_id, graph.total_facts, graph.critical_coverage_met,
            )
        except Exception as e:
            stage_row.status = "failed"
            stage_row.error_message = str(e)
            logger.error("research_graph FAILED | project=%d | %s", project_id, str(e)[:200])
        finally:
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)

        return stage_row

    def _run_content_plan_stage(self, project_id: int, *, force: bool = False) -> StageOutput:
        """Stage 3 — Content Plan: deterministic chapter depth planning."""
        from authoring.content_planner import ContentPlanner

        stage_row = self._make_v2_stage_row(project_id, "content_plan", force)
        if stage_row and stage_row.status == "complete":
            return stage_row

        project = self._project_svc.get(project_id)
        all_outputs = self.all_stage_outputs_as_dict(project_id)
        arch = all_outputs.get("system_architecture", {})
        research_graph = all_outputs.get("research_graph", {})

        brief = {"life_event": project.life_event or arch.get("life_event", ""), "audience": project.audience}
        strategy_blueprint = {
            "domains": [
                {"domain_id": d.get("id", ""), "name": d.get("name", ""), "operating_principles": []}
                for d in arch.get("control_domains", [])
            ],
            "risk_gates": [],
        }

        try:
            planner = ContentPlanner()
            plan = planner.build_content_plan(project_id, strategy_blueprint, research_graph, brief)
            stage_row.set_output(plan.model_dump())
            stage_row.preview_text = f"{len(plan.chapter_map)} chapters planned"
            stage_row.status = "complete"
            logger.info("content_plan COMPLETE | project=%d | chapters=%d", project_id, len(plan.chapter_map))
        except Exception as e:
            stage_row.status = "failed"
            stage_row.error_message = str(e)
            logger.error("content_plan FAILED | project=%d | %s", project_id, str(e)[:200])
        finally:
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)

        return stage_row

    def _run_voice_profile_stage(self, project_id: int, *, force: bool = False) -> StageOutput:
        """Stage 3b — Voice Profile: voice constraints and banned phrase list."""
        from authoring.content_planner import ContentPlanner

        stage_row = self._make_v2_stage_row(project_id, "voice_profile", force)
        if stage_row and stage_row.status == "complete":
            return stage_row

        project = self._project_svc.get(project_id)
        all_outputs = self.all_stage_outputs_as_dict(project_id)
        arch = all_outputs.get("system_architecture", {})

        brief = {
            "life_event": project.life_event or arch.get("life_event", ""),
            "audience": project.audience,
            "tone": project.tone or "professional",
        }
        strategy_blueprint = {
            "domains": [
                {"domain_id": d.get("id", ""), "name": d.get("name", ""), "operating_principles": []}
                for d in arch.get("control_domains", [])
            ],
        }

        try:
            planner = ContentPlanner()
            vp = planner.build_voice_profile(project_id, brief, strategy_blueprint)
            stage_row.set_output(vp.model_dump())
            stage_row.preview_text = (
                f"{len(vp.lexical_constraints)} constraints | "
                f"{len(vp.generic_phrase_blocklist)} banned phrases"
            )
            stage_row.status = "complete"
            logger.info(
                "voice_profile COMPLETE | project=%d | constraints=%d",
                project_id, len(vp.lexical_constraints),
            )
        except Exception as e:
            stage_row.status = "failed"
            stage_row.error_message = str(e)
            logger.error("voice_profile FAILED | project=%d | %s", project_id, str(e)[:200])
        finally:
            stage_row.updated_at = datetime.now(timezone.utc)
            self._repo.save(stage_row)

        return stage_row

    def run_full_pipeline(self, project_id: int) -> list[StageOutput]:
        import time as _time
        results: list[StageOutput] = []
        for stage in STAGE_NAMES:
            result = self.run_stage(project_id, stage)
            results.append(result)
            if result.status in ("failed", "schema_failed"):
                logger.warning(
                    "Pipeline halted at stage '%s' (status=%s)", stage, result.status
                )
                break
            # Brief pause between stages so back-to-back large calls
            # don't immediately saturate the token-per-minute window.
            _time.sleep(5)
        return results
