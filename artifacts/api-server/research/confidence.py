"""
Confidence scoring for research facts.

Scores each extracted fact based on:
  - Source type (authoritative / secondary / inferred)
  - Claim specificity (concrete values vs. vague assertions)
  - Jurisdiction alignment (fact tags match project jurisdiction)
  - Conflict presence (fact is contested by another source)

Produces a ConfidenceLevel (high / medium / low) with a numeric score 0.0–1.0.
Low-confidence facts below the configured threshold trigger a pause-with-questions
response rather than allowing them to flow into prose generation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from models.v2_artifacts import ConfidenceLevel


# ── Thresholds ─────────────────────────────────────────────────────────────────

LOW_CONFIDENCE_THRESHOLD: float = 0.35
MEDIUM_CONFIDENCE_THRESHOLD: float = 0.60

# Source type signals → base score contribution
SOURCE_TYPE_SCORES: dict[str, float] = {
    "government":     0.90,
    "legal":          0.85,
    "medical":        0.80,
    "financial":      0.75,
    "professional":   0.70,
    "secondary":      0.55,
    "general":        0.45,
    "inferred":       0.25,
    "unknown":        0.20,
}

# Vague hedge phrases that reduce confidence
VAGUE_PHRASES: list[str] = [
    "may", "might", "could", "sometimes", "often", "generally",
    "typically", "usually", "in some cases", "it depends", "varies",
    "possibly", "perhaps", "approximately",
]


@dataclass
class ConfidenceScore:
    score: float          # 0.0 – 1.0
    level: ConfidenceLevel
    reason: str
    flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 3),
            "level": self.level.value,
            "reason": self.reason,
            "flags": self.flags,
        }


def _detect_source_type(source: str) -> str:
    s = source.lower()
    if any(k in s for k in ("gov", "irs", "ssa", "cms", "medicare", "medicaid", "federal", "state")):
        return "government"
    if any(k in s for k in ("law", "statute", "code", "regulation", "attorney", "legal")):
        return "legal"
    if any(k in s for k in ("md", "hospital", "clinical", "health", "medical")):
        return "medical"
    if any(k in s for k in ("bank", "irs", "financial", "insurance", "401k", "trust")):
        return "financial"
    if any(k in s for k in ("certified", "professional", "association", "society")):
        return "professional"
    return "general"


def _claim_specificity(claim: str) -> float:
    """Higher score for claims with concrete values, dates, or legal citations."""
    bonus = 0.0
    if re.search(r"\d+", claim):
        bonus += 0.10
    if re.search(r"\b(must|shall|required|prohibited|deadline|within \d+)\b", claim, re.I):
        bonus += 0.10
    if re.search(r"\$[\d,]+|\d+%|\d+ days?|\d+ months?", claim):
        bonus += 0.10
    vague_count = sum(1 for p in VAGUE_PHRASES if p in claim.lower())
    penalty = min(vague_count * 0.08, 0.25)
    return max(0.0, min(bonus - penalty, 0.25))


def score_fact(
    claim: str,
    source: str,
    jurisdiction_tags: list[str],
    project_jurisdiction: str | None,
    conflict_flags: list[str],
) -> ConfidenceScore:
    """Compute a confidence score for a single extracted fact."""
    flags: list[str] = []

    source_type = _detect_source_type(source)
    base = SOURCE_TYPE_SCORES.get(source_type, 0.40)

    specificity_bonus = _claim_specificity(claim)
    score = base + specificity_bonus

    # Jurisdiction alignment bonus
    if project_jurisdiction and jurisdiction_tags:
        jur_lower = project_jurisdiction.lower()
        if any(jur_lower in tag.lower() for tag in jurisdiction_tags):
            score += 0.05
        else:
            score -= 0.05
            flags.append("jurisdiction_mismatch")

    # Conflict penalty
    if conflict_flags:
        score -= 0.15 * len(conflict_flags)
        flags.append(f"conflicts_with_{len(conflict_flags)}_source(s)")

    score = max(0.0, min(score, 1.0))

    if score >= MEDIUM_CONFIDENCE_THRESHOLD:
        level = ConfidenceLevel.HIGH
    elif score >= LOW_CONFIDENCE_THRESHOLD:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW
        flags.append("below_threshold")

    reason = f"source_type={source_type} base={base:.2f} specificity={specificity_bonus:+.2f}"
    return ConfidenceScore(score=score, level=level, reason=reason, flags=flags)


def generate_followup_questions(
    low_confidence_facts: list[dict[str, Any]],
    uncovered_entities: list[str],
) -> list[str]:
    """Generate clarifying questions for low-confidence facts and missing coverage."""
    questions: list[str] = []
    for fact in low_confidence_facts[:5]:
        questions.append(
            f"The claim \"{fact.get('claim', '')[:80]}\" has low confidence "
            f"(source: {fact.get('source', 'unknown')}). "
            "Can you provide a more authoritative source or confirm this applies to your situation?"
        )
    for entity in uncovered_entities[:5]:
        questions.append(
            f"No research coverage was found for \"{entity}\". "
            "Can you provide additional context or documentation for this?"
        )
    return questions
