"""
GraphBuilder — assembles the research_graph.json artifact (Stage 1 output).

Takes:
  - A ProjectBrief (entities, jurisdiction, life_event)
  - Retrieved passages from retrieval.py
  - Model-extracted or pure-Python extracted facts from fact_extractor.py

Produces:
  - A ResearchGraph with facts[], coverage_map[], conflict counts, and a
    critical_coverage_met gate.

Quality gate (PDR §04):
  Pipeline does not proceed to Stage 2 if critical entity coverage is below
  threshold. Threshold is configurable per event type.
"""
from __future__ import annotations

import uuid
from typing import Any

from core.logging import get_logger
from models.v2_artifacts import (
    ResearchGraph,
    ResearchFact,
    CoverageMapEntry,
    ConfidenceLevel,
)
from research.confidence import LOW_CONFIDENCE_THRESHOLD, generate_followup_questions
from research.fact_extractor import detect_conflicts, extract_facts_from_passage
from research.retrieval import retrieve_passages, RetrievedPassage

logger = get_logger(__name__)

# Minimum fraction of project entities that must have research coverage
# before the pipeline is allowed to proceed to Stage 2.
CRITICAL_COVERAGE_THRESHOLD: float = 0.50

# Per-event-type overrides (stricter for high-stakes events)
EVENT_COVERAGE_THRESHOLDS: dict[str, float] = {
    "eldercare":       0.65,
    "estate_planning": 0.65,
    "divorce":         0.60,
    "medical":         0.60,
    "real_estate":     0.55,
    "immigration":     0.60,
    "business":        0.50,
    "default":         0.50,
}


def _coverage_threshold(life_event_type: str) -> float:
    key = life_event_type.lower().replace(" ", "_").replace("-", "_")
    for event_key, threshold in EVENT_COVERAGE_THRESHOLDS.items():
        if event_key in key:
            return threshold
    return EVENT_COVERAGE_THRESHOLDS["default"]


def _extract_entity_keywords(brief: dict[str, Any]) -> list[str]:
    """Pull search keywords from the project brief for retrieval."""
    keywords: list[str] = []
    life_event = brief.get("life_event_type", "") or brief.get("life_event", "")
    if life_event:
        keywords.extend(life_event.lower().split())
    for person in brief.get("people", []):
        role = person.get("role", "")
        if role:
            keywords.append(role.lower())
    for system in brief.get("systems", []):
        keywords.extend(system.lower().split())
    keywords.extend(brief.get("jurisdiction_tags", []))
    return list(dict.fromkeys(keywords))  # deduplicate preserving order


def _build_coverage_map(
    facts: list[ResearchFact],
    brief: dict[str, Any],
) -> list[CoverageMapEntry]:
    """Map which project entities have at least one supporting fact."""
    covered_fact_ids_by_entity: dict[str, list[str]] = {}

    entities_to_check: list[tuple[str, str]] = []
    life_event = brief.get("life_event_type", "") or brief.get("life_event", "")
    if life_event:
        entities_to_check.append((life_event, "life_event"))
    for person in brief.get("people", []):
        name = person.get("name", "")
        role = person.get("role", "")
        if role:
            entities_to_check.append((role, "role"))
        if name:
            entities_to_check.append((name, "person"))
    for system in brief.get("systems", []):
        entities_to_check.append((system, "system"))

    for entity, entity_type in entities_to_check:
        entity_lower = entity.lower()
        matching_fact_ids = [
            f.fact_id for f in facts
            if entity_lower in f.claim.lower()
            or any(entity_lower in tag.lower() for tag in f.jurisdiction_tags)
        ]
        covered_fact_ids_by_entity[entity] = matching_fact_ids

    coverage_map: list[CoverageMapEntry] = []
    for (entity, entity_type), fact_ids in zip(
        entities_to_check,
        [covered_fact_ids_by_entity.get(e, []) for e, _ in entities_to_check],
    ):
        coverage_map.append(CoverageMapEntry(
            entity=entity,
            entity_type=entity_type,
            covered=len(fact_ids) > 0,
            fact_ids=fact_ids,
        ))

    return coverage_map


def build_research_graph(
    project_id: int,
    brief: dict[str, Any],
    *,
    additional_passages: list[RetrievedPassage] | None = None,
) -> tuple[ResearchGraph, list[str]]:
    """Build the research graph for a project.

    Args:
        project_id: The project being processed.
        brief: The normalized project brief dict.
        additional_passages: Optional passages from an external source (Phase D).

    Returns:
        (ResearchGraph, followup_questions)
        followup_questions is non-empty when critical coverage threshold is not met
        or when low-confidence facts need confirmation.
    """
    life_event = brief.get("life_event_type", "") or brief.get("life_event", "")
    jurisdiction = brief.get("jurisdiction")
    keywords = _extract_entity_keywords(brief)

    # Retrieve relevant passages
    passages = retrieve_passages(
        query_keywords=keywords,
        jurisdiction=jurisdiction,
        life_event=life_event,
        max_results=15,
    )
    if additional_passages:
        passages = passages + additional_passages

    logger.info(
        "research_graph | project=%d | retrieved %d passages | keywords=%s",
        project_id, len(passages), keywords[:6],
    )

    # Extract facts from passages
    all_facts: list[ResearchFact] = []
    for passage in passages:
        passage_facts = extract_facts_from_passage(passage, project_jurisdiction=jurisdiction)
        all_facts.extend(passage_facts)

    # Conflict detection across all facts
    all_facts = detect_conflicts(all_facts)

    # Build coverage map
    coverage_map = _build_coverage_map(all_facts, brief)
    covered_count = sum(1 for e in coverage_map if e.covered)
    total_entities = len(coverage_map)
    coverage_fraction = covered_count / max(total_entities, 1)

    low_confidence_facts = [
        f.model_dump() for f in all_facts
        if f.confidence == ConfidenceLevel.LOW
    ]
    conflict_count = sum(1 for f in all_facts if f.conflict_flags)

    # Quality gate check
    threshold = _coverage_threshold(life_event)
    critical_coverage_met = coverage_fraction >= threshold

    logger.info(
        "research_graph | project=%d | facts=%d | coverage=%.0f%% (threshold=%.0f%%) | "
        "low_conf=%d | conflicts=%d | gate=%s",
        project_id,
        len(all_facts),
        coverage_fraction * 100,
        threshold * 100,
        len(low_confidence_facts),
        conflict_count,
        "PASS" if critical_coverage_met else "FAIL",
    )

    # Generate follow-up questions if gate fails
    followup_questions: list[str] = []
    if not critical_coverage_met:
        uncovered = [e.entity for e in coverage_map if not e.covered]
        followup_questions = generate_followup_questions(low_confidence_facts, uncovered)
        logger.warning(
            "research_graph | project=%d | critical coverage gate FAILED — "
            "generated %d follow-up questions",
            project_id, len(followup_questions),
        )

    graph = ResearchGraph(
        project_id=project_id,
        facts=all_facts,
        coverage_map=coverage_map,
        total_facts=len(all_facts),
        low_confidence_count=len(low_confidence_facts),
        conflict_count=conflict_count,
        critical_coverage_met=critical_coverage_met,
    )

    return graph, followup_questions
