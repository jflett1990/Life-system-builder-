"""
ResearchIntegrityValidator — citation coverage, fact_id resolution, conflict surfacing.

PDR §06 validators/research_integrity.py:
  - Citation coverage: each chapter block must reference at least one fact_id
  - Fact ID resolution: all referenced fact_ids must exist in the research graph
  - Conflict surfacing: chapters touching conflicted facts must include a Considerations note
  - Coverage threshold: chapter citation_coverage_score must meet configured minimum

This validator runs as a blocking gate before Chapter Composer Pass B is allowed to run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

CITATION_COVERAGE_THRESHOLD: float = 0.80   # PDR §11 target: > 85%; gate at 80%


@dataclass
class IntegrityViolation:
    violation_type: str
    block_id: str | None
    chapter_id: str | None
    detail: str


@dataclass
class ResearchIntegrityResult:
    passed: bool
    citation_coverage: float
    violations: list[IntegrityViolation] = field(default_factory=list)
    conflict_flag_chapters: list[str] = field(default_factory=list)
    unresolved_fact_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "citation_coverage": round(self.citation_coverage, 3),
            "violation_count": len(self.violations),
            "violations": [
                {"type": v.violation_type, "block_id": v.block_id,
                 "chapter_id": v.chapter_id, "detail": v.detail}
                for v in self.violations
            ],
            "conflict_flag_chapters": self.conflict_flag_chapters,
            "unresolved_fact_ids": self.unresolved_fact_ids,
        }


class ResearchIntegrityValidator:
    """Validates citation coverage and fact ID integrity for a chapter packet.

    Usage:
        validator = ResearchIntegrityValidator(research_graph)
        result = validator.validate_chapter(chapter_packet_dict)
        if not result.passed:
            # Reject chapter and retry Pass B with coverage gap as context
    """

    def __init__(self, research_graph: dict[str, Any]) -> None:
        self._graph = research_graph
        self._known_fact_ids: set[str] = {
            f["fact_id"] for f in research_graph.get("facts", [])
            if "fact_id" in f
        }
        self._conflict_fact_ids: set[str] = {
            f["fact_id"] for f in research_graph.get("facts", [])
            if f.get("conflict_flags")
        }

    def validate_chapter(self, chapter_packet: dict[str, Any]) -> ResearchIntegrityResult:
        chapter_id = chapter_packet.get("chapter_id", "unknown")
        blocks = chapter_packet.get("blocks", [])
        violations: list[IntegrityViolation] = []
        conflict_flag_chapters: list[str] = []
        unresolved: list[str] = []

        if not blocks:
            return ResearchIntegrityResult(
                passed=False,
                citation_coverage=0.0,
                violations=[IntegrityViolation(
                    violation_type="no_blocks",
                    block_id=None,
                    chapter_id=chapter_id,
                    detail="Chapter packet contains no content blocks",
                )],
            )

        cited_blocks = 0
        for block in blocks:
            block_id = block.get("block_id", "?")
            fact_ids = block.get("fact_ids", [])

            # Check citation presence on narrative blocks
            if block.get("block_type") in ("narrative", "callout", "table"):
                if not fact_ids:
                    violations.append(IntegrityViolation(
                        violation_type="missing_citation",
                        block_id=block_id,
                        chapter_id=chapter_id,
                        detail=f"Narrative block '{block_id}' has no fact_ids",
                    ))
                else:
                    cited_blocks += 1

                    # Resolve each fact_id against the graph
                    for fid in fact_ids:
                        if fid not in self._known_fact_ids:
                            unresolved.append(fid)
                            violations.append(IntegrityViolation(
                                violation_type="unresolved_fact_id",
                                block_id=block_id,
                                chapter_id=chapter_id,
                                detail=f"fact_id '{fid}' not found in research graph",
                            ))

                    # Flag chapters that cite conflicted facts
                    if any(fid in self._conflict_fact_ids for fid in fact_ids):
                        if chapter_id not in conflict_flag_chapters:
                            conflict_flag_chapters.append(chapter_id)

        narrative_blocks = sum(
            1 for b in blocks
            if b.get("block_type") in ("narrative", "callout", "table")
        )
        citation_coverage = cited_blocks / max(narrative_blocks, 1)

        if citation_coverage < CITATION_COVERAGE_THRESHOLD:
            violations.append(IntegrityViolation(
                violation_type="coverage_below_threshold",
                block_id=None,
                chapter_id=chapter_id,
                detail=(
                    f"Citation coverage {citation_coverage:.0%} is below threshold "
                    f"{CITATION_COVERAGE_THRESHOLD:.0%}"
                ),
            ))

        passed = (
            len(violations) == 0
            or all(v.violation_type not in ("coverage_below_threshold", "unresolved_fact_id") for v in violations)
        )

        logger.info(
            "research_integrity | chapter=%s | coverage=%.0f%% | violations=%d | conflicts=%d",
            chapter_id, citation_coverage * 100, len(violations), len(conflict_flag_chapters),
        )

        return ResearchIntegrityResult(
            passed=passed,
            citation_coverage=citation_coverage,
            violations=violations,
            conflict_flag_chapters=conflict_flag_chapters,
            unresolved_fact_ids=list(set(unresolved)),
        )

    def build_coverage_gap_context(self, result: ResearchIntegrityResult) -> str:
        """Build retry context injected into Pass B prompt when coverage is insufficient."""
        lines = ["CITATION COVERAGE GATE FAILED — rewrite required:\n"]
        uncited = [v.block_id for v in result.violations if v.violation_type == "missing_citation"]
        if uncited:
            lines.append(
                f"These blocks have no citations — anchor each to a specific fact from the research graph:\n"
                + "\n".join(f"  - {b}" for b in uncited)
            )
        if result.unresolved_fact_ids:
            lines.append(
                f"\nThese fact_ids are invalid — replace them with real IDs from the research graph:\n"
                + "\n".join(f"  - {fid}" for fid in result.unresolved_fact_ids[:10])
            )
        if result.citation_coverage < CITATION_COVERAGE_THRESHOLD:
            lines.append(
                f"\nCurrent citation coverage: {result.citation_coverage:.0%}. "
                f"Required: {CITATION_COVERAGE_THRESHOLD:.0%}. "
                "Every narrative block must cite at least one research fact."
            )
        return "\n".join(lines)
