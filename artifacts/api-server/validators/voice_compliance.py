"""
VoiceComplianceValidator — genericity guard, banned phrase detection, terminology quotas.

PDR §06 validators/voice_compliance.py:
  Wraps GenericityGuard with batch validation across multiple chapter blocks
  and provides the pipeline integration point for voice compliance reporting.

  Terminology quota check: if the voice profile specifies required terms,
  at least N% of chapters must contain each required term.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from authoring.genericity_guard import GenericityGuard, GuardResult
from core.logging import get_logger

logger = get_logger(__name__)

REQUIRED_TERM_COVERAGE_THRESHOLD: float = 0.60  # 60% of chapters must include each required term


@dataclass
class VoiceComplianceResult:
    passed: bool
    chapter_results: dict[str, GuardResult] = field(default_factory=dict)
    term_coverage: dict[str, float] = field(default_factory=dict)
    term_coverage_failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "chapter_count": len(self.chapter_results),
            "chapters_failed": sum(1 for r in self.chapter_results.values() if not r.passed),
            "term_coverage": {k: round(v, 3) for k, v in self.term_coverage.items()},
            "term_coverage_failures": self.term_coverage_failures,
        }


class VoiceComplianceValidator:
    """Batch voice compliance validator across all chapter packets.

    Usage:
        vcv = VoiceComplianceValidator(project_id=42, voice_profile=vp_dict)
        result = vcv.validate_chapters(chapter_packets)
    """

    def __init__(self, project_id: int, voice_profile: dict[str, Any]) -> None:
        self._project_id = project_id
        self._voice_profile = voice_profile
        self._required_terms = [
            c["value"].lower()
            for c in voice_profile.get("lexical_constraints", [])
            if c.get("constraint_type") == "required_term"
        ]

    def validate_chapter_text(self, chapter_id: str, text: str) -> GuardResult:
        """Validate a single chapter's prose. Returns GuardResult."""
        guard = GenericityGuard(
            project_id=self._project_id,
            voice_profile=self._voice_profile,
        )
        result = guard.check(text)
        if not result.passed:
            logger.info(
                "voice_compliance | project=%d | chapter=%s | FAIL | violations=%d",
                self._project_id, chapter_id, len(result.violations),
            )
        return result

    def validate_chapters(
        self,
        chapter_packets: list[dict[str, Any]],
    ) -> VoiceComplianceResult:
        """Run guard across all chapter packets and check required term quotas."""
        chapter_results: dict[str, GuardResult] = {}

        for packet in chapter_packets:
            chapter_id = packet.get("chapter_id", "unknown")
            # Concatenate all block content for voice checking
            all_text = " ".join(
                b.get("content", "") for b in packet.get("blocks", [])
                if isinstance(b.get("content"), str)
            )
            if all_text.strip():
                chapter_results[chapter_id] = self.validate_chapter_text(chapter_id, all_text)

        # Term coverage check
        term_coverage: dict[str, float] = {}
        term_coverage_failures: list[str] = []
        total_chapters = max(len(chapter_packets), 1)

        for term in self._required_terms:
            chapters_with_term = sum(
                1 for packet in chapter_packets
                if term in " ".join(
                    b.get("content", "") for b in packet.get("blocks", [])
                    if isinstance(b.get("content"), str)
                ).lower()
            )
            coverage = chapters_with_term / total_chapters
            term_coverage[term] = coverage
            if coverage < REQUIRED_TERM_COVERAGE_THRESHOLD:
                term_coverage_failures.append(term)

        all_passed = all(r.passed for r in chapter_results.values())
        no_term_failures = len(term_coverage_failures) == 0
        passed = all_passed and no_term_failures

        logger.info(
            "voice_compliance | project=%d | chapters=%d | failed=%d | term_failures=%d",
            self._project_id,
            len(chapter_results),
            sum(1 for r in chapter_results.values() if not r.passed),
            len(term_coverage_failures),
        )

        return VoiceComplianceResult(
            passed=passed,
            chapter_results=chapter_results,
            term_coverage=term_coverage,
            term_coverage_failures=term_coverage_failures,
        )
