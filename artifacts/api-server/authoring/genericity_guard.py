"""
GenericityGuard — blocking validator for voice compliance and banned phrases.

PDR §04 Stage 3 — "Voice as a Hard Gate":
  The voice profile is not advisory. Outputs that hit banned phrases or miss
  required terminology are rejected and requeued with the violation as context.
  Retry budget: 2 attempts before the block is flagged but allowed through.

PDR §09 — Negative Prompt Memory:
  After each chapter generation run, rejected phrases are added to a
  project-scoped banned phrase list that persists across all subsequent
  generation calls in that project.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# ── Built-in generic phrase blocklist (common LLM filler) ─────────────────────

GLOBAL_GENERIC_PHRASES: list[str] = [
    "it's important to note",
    "it is important to note",
    "it's worth noting",
    "as mentioned earlier",
    "as previously discussed",
    "in conclusion",
    "in summary",
    "to summarize",
    "in today's world",
    "in today's fast-paced world",
    "needless to say",
    "it goes without saying",
    "first and foremost",
    "last but not least",
    "at the end of the day",
    "when all is said and done",
    "moving forward",
    "going forward",
    "leverage",                      # business jargon filler
    "synergies",
    "holistic approach",
    "empower",
    "streamline",
    "paradigm shift",
    "best practices",                 # acceptable only with specifics — blocked bare
    "game changer",
    "in this regard",
    "with that being said",
    "that being said",
    "having said that",
    "on the other hand",             # too frequent as a pure filler
    "it's crucial to",
    "it is crucial to",
    "it's essential to",
    "it is essential to",
    "you need to understand",
    "you must understand",
    "keep in mind that",
    "rest assured",
    "don't hesitate to",
    "please note that",
    "as you can see",
    "quite simply",
    "absolutely",                    # as a sentence-leading affirmation
    "certainly",                     # as a sentence-leading affirmation
    "of course",
    "obviously",
    "clearly",
]


# ── Per-project negative prompt memory ────────────────────────────────────────

# Maps project_id → list of additional banned phrases accumulated during generation.
_project_banned_phrases: dict[int, list[str]] = {}


def get_project_banned_phrases(project_id: int) -> list[str]:
    return list(_project_banned_phrases.get(project_id, []))


def record_rejected_phrases(project_id: int, phrases: list[str]) -> None:
    """Add rejected phrases to the project-scoped negative prompt memory."""
    existing = _project_banned_phrases.setdefault(project_id, [])
    for phrase in phrases:
        phrase_lower = phrase.lower().strip()
        if phrase_lower and phrase_lower not in existing:
            existing.append(phrase_lower)
    logger.debug(
        "genericity_guard | project=%d | negative_memory now %d phrases",
        project_id, len(existing),
    )


# ── Violation dataclass ────────────────────────────────────────────────────────

@dataclass
class GuardViolation:
    violation_type: str    # banned_phrase | missing_required_term | tone_violation
    matched_phrase: str
    context_snippet: str   # surrounding text for rewrite context
    position: int          # character offset


@dataclass
class GuardResult:
    passed: bool
    violations: list[GuardViolation] = field(default_factory=list)
    retry_context: str = ""   # injected into the rewrite prompt as negative context

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violation_count": len(self.violations),
            "violations": [
                {
                    "type": v.violation_type,
                    "matched_phrase": v.matched_phrase,
                    "context_snippet": v.context_snippet,
                }
                for v in self.violations
            ],
            "retry_context": self.retry_context,
        }


# ── GenericityGuard ────────────────────────────────────────────────────────────

class GenericityGuard:
    """Validates generated prose against the voice profile and banned phrase list.

    Usage:
        guard = GenericityGuard(project_id=42, voice_profile=vp_dict)
        result = guard.check(prose_text)
        if not result.passed:
            # retry with result.retry_context injected as negative prompt
    """

    def __init__(
        self,
        project_id: int,
        voice_profile: dict[str, Any] | None = None,
    ) -> None:
        self._project_id = project_id
        self._voice_profile = voice_profile or {}
        self._banned: list[str] = self._build_banned_list()
        self._required: list[str] = self._build_required_list()

    def _build_banned_list(self) -> list[str]:
        banned = list(GLOBAL_GENERIC_PHRASES)
        # Add voice_profile lexical constraints
        for constraint in self._voice_profile.get("lexical_constraints", []):
            if constraint.get("constraint_type") == "banned_phrase":
                phrase = constraint.get("value", "").lower().strip()
                if phrase and phrase not in banned:
                    banned.append(phrase)
        # Add project-scoped negative prompt memory
        banned.extend(get_project_banned_phrases(self._project_id))
        # Add profile's own generic_phrase_blocklist
        for phrase in self._voice_profile.get("generic_phrase_blocklist", []):
            phrase_lower = phrase.lower().strip()
            if phrase_lower and phrase_lower not in banned:
                banned.append(phrase_lower)
        return banned

    def _build_required_list(self) -> list[str]:
        required: list[str] = []
        for constraint in self._voice_profile.get("lexical_constraints", []):
            if constraint.get("constraint_type") == "required_term":
                term = constraint.get("value", "").lower().strip()
                if term:
                    required.append(term)
        return required

    def check(self, text: str) -> GuardResult:
        text_lower = text.lower()
        violations: list[GuardViolation] = []

        # Check banned phrases
        for phrase in self._banned:
            for match in re.finditer(re.escape(phrase), text_lower):
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                violations.append(GuardViolation(
                    violation_type="banned_phrase",
                    matched_phrase=phrase,
                    context_snippet=text[start:end].strip(),
                    position=match.start(),
                ))

        # Check required terms
        for term in self._required:
            if term not in text_lower:
                violations.append(GuardViolation(
                    violation_type="missing_required_term",
                    matched_phrase=term,
                    context_snippet="",
                    position=-1,
                ))

        if violations:
            banned_found = [v.matched_phrase for v in violations if v.violation_type == "banned_phrase"]
            missing = [v.matched_phrase for v in violations if v.violation_type == "missing_required_term"]

            # Record rejected phrases into negative prompt memory
            if banned_found:
                record_rejected_phrases(self._project_id, banned_found)

            retry_context = self._build_retry_context(banned_found, missing)
            logger.info(
                "genericity_guard | project=%d | FAIL | banned=%d missing=%d",
                self._project_id, len(banned_found), len(missing),
            )
            return GuardResult(passed=False, violations=violations, retry_context=retry_context)

        logger.debug("genericity_guard | project=%d | PASS", self._project_id)
        return GuardResult(passed=True)

    def _build_retry_context(
        self, banned_found: list[str], missing_required: list[str]
    ) -> str:
        parts: list[str] = ["GENERICITY GUARD REJECTION — rewrite required:\n"]
        if banned_found:
            unique_banned = list(dict.fromkeys(banned_found))[:10]
            parts.append(
                "REMOVE these generic/banned phrases entirely — do not paraphrase them:\n"
                + "\n".join(f"  - \"{p}\"" for p in unique_banned)
            )
        if missing_required:
            parts.append(
                "\nINCLUDE these required domain terms naturally in the rewrite:\n"
                + "\n".join(f"  - \"{t}\"" for t in missing_required)
            )
        parts.append(
            "\nWrite with concrete specificity. Use exact figures, deadlines, and actions. "
            "Eliminate all hedge language and meta-commentary about the document itself."
        )
        return "\n".join(parts)

    def check_with_retry_budget(
        self,
        text: str,
        max_retries: int = 2,
    ) -> tuple[GuardResult, bool]:
        """Run the guard. Returns (result, should_retry).

        should_retry=True means a rewrite call is warranted and within budget.
        should_retry=False means either passed or retry budget exhausted.
        """
        result = self.check(text)
        if result.passed:
            return result, False
        # Within budget — caller should retry with result.retry_context
        return result, max_retries > 0
