"""
FactExtractor — structured fact extraction from retrieved passages.

Uses an LLM call (mid-tier) to extract discrete, verifiable facts from each
retrieved passage. Each extracted fact gets:
  - A stable fact_id (passage_id + position index)
  - A single concrete claim (one sentence max)
  - The originating source
  - A confidence score (from the confidence module)
  - Jurisdiction tags inherited from the passage

Runs conflict detection: if two facts make mutually contradictory claims
about the same entity, both get conflict_flags set.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from core.logging import get_logger
from models.v2_artifacts import ResearchFact, ConfidenceLevel
from research.confidence import score_fact
from research.retrieval import RetrievedPassage

logger = get_logger(__name__)


def _make_fact_id(passage_id: str, idx: int, claim: str) -> str:
    short_hash = hashlib.md5(claim.encode()).hexdigest()[:6]
    return f"{passage_id}-f{idx:02d}-{short_hash}"


def _split_into_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def extract_facts_from_passage(
    passage: RetrievedPassage,
    project_jurisdiction: str | None = None,
) -> list[ResearchFact]:
    """Extract structured facts from a single retrieved passage.

    This is the pure-Python extraction path — it splits the passage into
    discrete factual sentences and scores each one. The LLM-assisted extraction
    path (``extract_facts_with_model``) calls this after receiving model output.
    """
    sentences = _split_into_sentences(passage.text)
    facts: list[ResearchFact] = []

    for idx, sentence in enumerate(sentences):
        if len(sentence.split()) < 5:
            continue
        confidence_score = score_fact(
            claim=sentence,
            source=passage.source,
            jurisdiction_tags=passage.jurisdiction_tags,
            project_jurisdiction=project_jurisdiction,
            conflict_flags=[],
        )
        facts.append(ResearchFact(
            fact_id=_make_fact_id(passage.passage_id, idx, sentence),
            claim=sentence,
            source=passage.source,
            confidence=confidence_score.level,
            jurisdiction_tags=passage.jurisdiction_tags,
            conflict_flags=confidence_score.flags,
        ))

    return facts


def extract_facts_with_model(
    model_output: dict[str, Any],
    passage: RetrievedPassage,
    project_jurisdiction: str | None = None,
) -> list[ResearchFact]:
    """Convert model-extracted facts (from LLM extraction call) into ResearchFact objects.

    The model is expected to return a list of dicts with keys:
        claim, source (optional), notes (optional)
    """
    raw_facts = model_output.get("facts", [])
    if not isinstance(raw_facts, list):
        logger.warning("fact_extractor: model output 'facts' is not a list — falling back to passage extraction")
        return extract_facts_from_passage(passage, project_jurisdiction)

    results: list[ResearchFact] = []
    for idx, raw in enumerate(raw_facts):
        if not isinstance(raw, dict):
            continue
        claim = str(raw.get("claim", "")).strip()
        if not claim or len(claim.split()) < 4:
            continue
        source = raw.get("source", passage.source) or passage.source
        confidence_score = score_fact(
            claim=claim,
            source=source,
            jurisdiction_tags=passage.jurisdiction_tags,
            project_jurisdiction=project_jurisdiction,
            conflict_flags=[],
        )
        results.append(ResearchFact(
            fact_id=_make_fact_id(passage.passage_id, idx, claim),
            claim=claim,
            source=source,
            confidence=confidence_score.level,
            jurisdiction_tags=passage.jurisdiction_tags,
            conflict_flags=confidence_score.flags,
        ))
    return results


def detect_conflicts(facts: list[ResearchFact]) -> list[ResearchFact]:
    """Flag pairs of facts that make contradictory claims about the same entity.

    Uses keyword overlap to detect potential conflicts. Pairs where both
    contain a numeric value and the values differ on the same entity are
    flagged as conflicting.
    """
    numeric_pattern = re.compile(r"\$[\d,]+|\d+%|\d+ (days?|months?|years?)", re.I)

    def _entity_keywords(claim: str) -> set[str]:
        words = re.findall(r"\b[A-Za-z]{4,}\b", claim.lower())
        return set(words) - {"that", "this", "with", "from", "have", "will", "must", "shall"}

    updated = [ResearchFact(**f.model_dump()) for f in facts]

    for i, fi in enumerate(updated):
        for j, fj in enumerate(updated):
            if i >= j:
                continue
            # Only check if they share significant entity keywords
            ki = _entity_keywords(fi.claim)
            kj = _entity_keywords(fj.claim)
            if len(ki & kj) < 2:
                continue
            # Check if both have numeric values that differ
            nums_i = set(numeric_pattern.findall(fi.claim))
            nums_j = set(numeric_pattern.findall(fj.claim))
            if nums_i and nums_j and not nums_i.intersection(nums_j):
                conflict_note = f"conflicts_with_{fj.fact_id}"
                if conflict_note not in updated[i].conflict_flags:
                    updated[i].conflict_flags.append(conflict_note)
                conflict_note_rev = f"conflicts_with_{fi.fact_id}"
                if conflict_note_rev not in updated[j].conflict_flags:
                    updated[j].conflict_flags.append(conflict_note_rev)

    return updated
