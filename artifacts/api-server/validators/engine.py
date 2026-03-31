"""
ValidationEngine — orchestrates all rule sets and computes the final verdict.

Architecture:
  1. Run per-stage rules against each completed stage output
  2. Run cross-stage rules against the full context dict
  3. Compute verdict: pass | conditional_pass | fail
  4. Build ValidationResult with per-stage summaries and flat defect list
  5. Optionally persist result to database

Verdict logic:
  fail             — any Severity.fatal defect, OR any Severity.error defect where
                     blocked_handoff=True, OR any Severity.error at all
  conditional_pass — only Severity.warning or Severity.info defects
  pass             — zero defects
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from validators.defect import Defect, Severity, Verdict, compute_verdict, sort_defects, SEVERITY_ORDER
from validators.rules.system_architecture import SYSTEM_ARCHITECTURE_RULES
from validators.rules.worksheet_system    import WORKSHEET_SYSTEM_RULES
from validators.rules.layout_mapping      import LAYOUT_MAPPING_RULES
from validators.rules.render_blueprint    import RENDER_BLUEPRINT_RULES
from validators.rules.cross_stage         import CROSS_STAGE_RULES
from validators.rules.base                import BaseRule
from core.logging import get_logger

logger = get_logger(__name__)

STAGE_RULE_MAP: dict[str, list[BaseRule]] = {
    "system_architecture": SYSTEM_ARCHITECTURE_RULES,
    "worksheet_system":    WORKSHEET_SYSTEM_RULES,
    "layout_mapping":      LAYOUT_MAPPING_RULES,
    "render_blueprint":    RENDER_BLUEPRINT_RULES,
}


class StageValidationResult:
    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.defects: list[Defect] = []

    def add(self, defect: Defect) -> None:
        self.defects.append(defect)

    @property
    def verdict(self) -> str:
        return compute_verdict(self.defects).value

    @property
    def fatal_count(self) -> int:
        return sum(1 for d in self.defects if d.severity == Severity.fatal)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.defects if d.severity == Severity.error)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.defects if d.severity == Severity.warning)

    @property
    def info_count(self) -> int:
        return sum(1 for d in self.defects if d.severity == Severity.info)

    def to_dict(self) -> dict:
        return {
            "stage":         self.stage,
            "status":        self.verdict,
            "defect_count":  len(self.defects),
            "fatal_count":   self.fatal_count,
            "error_count":   self.error_count,
            "warning_count": self.warning_count,
            "info_count":    self.info_count,
            "defects":       [d.to_dict() for d in sort_defects(self.defects)],
        }


class ValidationResult:
    def __init__(
        self,
        project_id: int,
        stage_results: dict[str, StageValidationResult],
        all_defects: list[Defect],
        skipped_stages: list[str],
    ) -> None:
        self.project_id = project_id
        self.stage_results = stage_results
        self.all_defects = sort_defects(all_defects)
        self.skipped_stages = skipped_stages
        self.validated_at = datetime.now(timezone.utc)

    @property
    def verdict(self) -> Verdict:
        return compute_verdict(self.all_defects)

    @property
    def blocked_handoff(self) -> bool:
        return any(d.blocked_handoff for d in self.all_defects)

    @property
    def fatal_count(self) -> int:
        return sum(1 for d in self.all_defects if d.severity == Severity.fatal)

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.all_defects if d.severity == Severity.error)

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.all_defects if d.severity == Severity.warning)

    @property
    def info_count(self) -> int:
        return sum(1 for d in self.all_defects if d.severity == Severity.info)

    def _build_summary(self) -> str:
        verdict = self.verdict
        total = len(self.all_defects)
        if verdict == Verdict.passed:
            return (
                "PASS — All pipeline stages passed compiler validation. "
                "Zero defects detected. Output is render-ready and cleared for handoff."
            )
        if verdict == Verdict.conditional_pass:
            return (
                f"CONDITIONAL PASS — {self.warning_count} warning(s) detected across "
                f"{len(self.stage_results)} stage(s). No handoff blockers. "
                "Document can proceed to render but defects should be reviewed."
            )
        # fail
        blocker_stages = sorted({
            d.stage for d in self.all_defects
            if d.blocked_handoff and d.severity in (Severity.fatal, Severity.error)
        })
        return (
            f"FAIL — {total} defect(s): {self.fatal_count} fatal, {self.error_count} error(s), "
            f"{self.warning_count} warning(s). "
            f"Handoff blocked by defects in: {', '.join(blocker_stages) or 'see defect list'}. "
            "All fatal and error defects must be resolved before rendering."
        )

    def to_dict(self) -> dict:
        stage_list = [sr.to_dict() for sr in self.stage_results.values()]
        for skip in self.skipped_stages:
            stage_list.append({
                "stage": skip, "status": "skipped",
                "defect_count": 0, "fatal_count": 0,
                "error_count": 0, "warning_count": 0, "info_count": 0,
                "defects": [],
            })
        return {
            "project_id":    self.project_id,
            "verdict":       self.verdict.value,
            "blocked_handoff": self.blocked_handoff,
            "total_defects": len(self.all_defects),
            "fatal_count":   self.fatal_count,
            "error_count":   self.error_count,
            "warning_count": self.warning_count,
            "info_count":    self.info_count,
            "summary":       self._build_summary(),
            "stages":        stage_list,
            "defects":       [d.to_dict() for d in self.all_defects],
            "skipped_stages": self.skipped_stages,
            "validated_at":  self.validated_at.isoformat(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class ValidationEngine:
    """
    Runs all registered rule sets against pipeline stage outputs and returns
    a structured ValidationResult.

    Usage:
        engine = ValidationEngine()
        result = engine.run(project_id=1, stage_outputs=all_outputs)
    """

    def run(
        self,
        project_id: int,
        stage_outputs: dict[str, Any],
    ) -> ValidationResult:
        """
        Args:
            project_id:     The project being validated.
            stage_outputs:  Dict of stage_name → parsed JSON output.
                            Only completed stages are expected.

        Returns:
            ValidationResult with verdict, per-stage summaries, and flat defect list.
        """
        stage_results: dict[str, StageValidationResult] = {}
        all_defects: list[Defect] = []
        skipped_stages: list[str] = []

        # Build context dict shared across all rules
        context = dict(stage_outputs)
        context["project_id"] = project_id

        # Per-stage rules
        for stage, rules in STAGE_RULE_MAP.items():
            if stage not in stage_outputs:
                skipped_stages.append(stage)
                logger.debug("Stage '%s' not in outputs — skipping", stage)
                continue

            stage_result = StageValidationResult(stage)
            stage_output = stage_outputs[stage]

            logger.debug("Validating stage '%s' with %d rules", stage, len(rules))
            for rule in rules:
                try:
                    defects = rule.check(stage_output, context)
                    for d in defects:
                        stage_result.add(d)
                        all_defects.append(d)
                except Exception as e:
                    logger.error(
                        "Rule '%s' raised exception on stage '%s': %s",
                        rule.rule_id, stage, e, exc_info=True,
                    )

            stage_results[stage] = stage_result
            logger.info(
                "Stage '%s' validation: %s | %d defect(s)",
                stage, stage_result.verdict, len(stage_result.defects),
            )

        # Cross-stage rules — only run when at least 2 stages are present
        if len(stage_outputs) >= 2:
            cross_result = StageValidationResult("cross_stage")
            for rule in CROSS_STAGE_RULES:
                try:
                    defects = rule.check(stage_output={}, context=context)
                    for d in defects:
                        cross_result.add(d)
                        all_defects.append(d)
                        # Attach cross-stage defects to their target stage result too
                        if d.stage in stage_results:
                            stage_results[d.stage].add(d)
                except Exception as e:
                    logger.error("Cross-stage rule '%s' raised: %s", rule.rule_id, e, exc_info=True)

            if cross_result.defects:
                stage_results["cross_stage"] = cross_result
                logger.info(
                    "Cross-stage validation: %d defect(s)", len(cross_result.defects),
                )

        result = ValidationResult(
            project_id=project_id,
            stage_results=stage_results,
            all_defects=all_defects,
            skipped_stages=skipped_stages,
        )

        logger.info(
            "Validation complete: project=%d verdict=%s defects=%d (fatal=%d error=%d warning=%d)",
            project_id,
            result.verdict.value,
            len(all_defects),
            result.fatal_count,
            result.error_count,
            result.warning_count,
        )
        return result
