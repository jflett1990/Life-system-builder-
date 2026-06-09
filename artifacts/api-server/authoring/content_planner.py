"""
ContentPlanner — Stage 3: Content Plan + Voice Profile generation.

PDR §04 Stage 3:
  Separates planning from writing. Defines WHAT to write and HOW it should sound
  before any chapter prose is generated.

  content_plan.json:
    - chapter_map: ordered chapters with depth targets, required components,
      citation quotas, and adaptive depth_weight (0.5–2.0 multiplier)
    - component_choices: which block types appear in each chapter

  voice_profile.json:
    - lexical_constraints: banned phrases, required domain terms, tone descriptors
    - audience_profile: reading level, assumed knowledge, emotional context
    - generic_phrase_blocklist: built at generation time, persistent across chapters

Adaptive depth engine (PDR §09):
  Domains with higher research coverage and risk gate count get deeper chapters.
  depth_weight = 0.5 (low risk, sparse coverage) to 2.0 (high risk, full coverage).
"""
from __future__ import annotations

import math
from typing import Any

from core.logging import get_logger
from models.v2_artifacts import (
    ContentPlan,
    VoiceProfile,
    ChapterMapEntry,
    ComponentChoice,
    BlockType,
    LexicalConstraint,
    AudienceProfile,
)
from authoring.genericity_guard import GLOBAL_GENERIC_PHRASES

logger = get_logger(__name__)


# ── Depth weight computation ───────────────────────────────────────────────────

def _compute_depth_weight(
    domain_id: str,
    research_graph: dict[str, Any],
    risk_gates: list[dict[str, Any]],
) -> float:
    """Compute adaptive depth_weight for a domain.

    Higher coverage + more risk gates → deeper chapter (up to 2.0×).
    Low coverage + no risk gates → compressed chapter (0.5×).
    """
    # Count facts covering this domain
    facts = research_graph.get("facts", [])
    domain_facts = sum(
        1 for f in facts
        if domain_id.lower() in " ".join(f.get("jurisdiction_tags", [])).lower()
        or domain_id.lower() in f.get("claim", "").lower()
    )
    coverage_score = min(domain_facts / max(len(facts), 1) * 5, 1.0)

    # Count risk gates for this domain
    domain_gates = sum(
        1 for g in risk_gates
        if domain_id.lower() in g.get("condition", "").lower()
        or domain_id.lower() in " ".join(g.get("cascade_triggers", [])).lower()
    )
    gate_score = min(domain_gates / 3, 1.0)

    # Combined weight: 0.5 baseline + up to 1.5 additional
    raw_weight = 0.5 + (coverage_score * 0.75) + (gate_score * 0.75)
    return round(min(max(raw_weight, 0.5), 2.0), 2)


# ── Default component choices per chapter type ─────────────────────────────────

def _standard_components(citation_quota: int) -> list[ComponentChoice]:
    return [
        ComponentChoice(component_type=BlockType.NARRATIVE, required=True, citation_quota=citation_quota),
        ComponentChoice(component_type=BlockType.CALLOUT, required=False, citation_quota=0),
        ComponentChoice(component_type=BlockType.LIST, required=True, citation_quota=0),
    ]


def _table_components(citation_quota: int) -> list[ComponentChoice]:
    return [
        ComponentChoice(component_type=BlockType.NARRATIVE, required=True, citation_quota=citation_quota),
        ComponentChoice(component_type=BlockType.TABLE, required=True, citation_quota=0),
        ComponentChoice(component_type=BlockType.CALLOUT, required=False, citation_quota=0),
    ]


# ── ContentPlanner ─────────────────────────────────────────────────────────────

class ContentPlanner:
    """Generates ContentPlan and VoiceProfile from strategy blueprint + research graph.

    Phase C: deterministic generation from the blueprint data.
    Phase D: will add an LLM call for voice profile style marker extraction.
    """

    def build_content_plan(
        self,
        project_id: int,
        strategy_blueprint: dict[str, Any],
        research_graph: dict[str, Any],
        brief: dict[str, Any],
    ) -> ContentPlan:
        domains = strategy_blueprint.get("domains", [])
        risk_gates = strategy_blueprint.get("risk_gates", [])
        total_facts = len(research_graph.get("facts", []))
        base_citation_quota = max(1, total_facts // max(len(domains), 1))

        chapter_map: list[ChapterMapEntry] = []
        for i, domain in enumerate(domains):
            domain_id = domain.get("domain_id", f"d{i+1:02d}")
            domain_name = domain.get("name", f"Domain {i+1}")
            depth_weight = _compute_depth_weight(domain_id, research_graph, risk_gates)
            depth_target = max(1, math.ceil(2 * depth_weight))
            has_risk = any(
                domain_id.lower() in g.get("condition", "").lower()
                for g in risk_gates
            )
            components = _table_components(base_citation_quota) if has_risk else _standard_components(base_citation_quota)

            chapter_map.append(ChapterMapEntry(
                chapter_id=f"ch-{domain_id}",
                domain_id=domain_id,
                title=domain_name,
                depth_target=depth_target,
                depth_weight=depth_weight,
                required_components=components,
                citation_quota=base_citation_quota,
            ))

        logger.info(
            "content_planner | project=%d | %d chapters | depth_weights=%s",
            project_id, len(chapter_map),
            [c.depth_weight for c in chapter_map],
        )

        return ContentPlan(
            project_id=project_id,
            chapter_map=chapter_map,
            component_choices=_standard_components(base_citation_quota),
        )

    def build_voice_profile(
        self,
        project_id: int,
        brief: dict[str, Any],
        strategy_blueprint: dict[str, Any],
    ) -> VoiceProfile:
        topic = brief.get("topic_type", "") or brief.get("topic", "")
        audience = brief.get("audience", "self-directed learners and developers")
        tone = brief.get("tone", "clear, practical, encouraging")

        # Build lexical constraints from the tutorial topic
        constraints: list[LexicalConstraint] = [
            LexicalConstraint(
                constraint_type="tone_descriptor",
                value=tone,
                reason="Set by project intake",
            ),
        ]

        # Add domain-specific required terms from blueprint
        for domain in strategy_blueprint.get("domains", []):
            for principle in domain.get("operating_principles", [])[:2]:
                if len(principle.split()) <= 4:
                    constraints.append(LexicalConstraint(
                        constraint_type="required_term",
                        value=principle.lower(),
                        reason=f"Operating principle for domain {domain.get('name', '')}",
                    ))

        # Reading level and assumed knowledge from audience field
        reading_level = "professional" if "professional" in (audience or "").lower() else "general"
        assumed_knowledge: list[str] = []
        topic_lower = topic.lower()
        if any(kw in topic_lower for kw in ["deploy", "docker", "hosting", "ci/cd"]):
            assumed_knowledge.append("basic terminal usage and git")
        if any(kw in topic_lower for kw in ["react", "next", "vue", "frontend", "landing"]):
            assumed_knowledge.append("basic HTML/CSS/JavaScript")
        if any(kw in topic_lower for kw in ["python", "bot", "fastapi", "script"]):
            assumed_knowledge.append("basic Python syntax")
        if any(kw in topic_lower for kw in ["api", "database", "crud", "supabase", "sql"]):
            assumed_knowledge.append("basic idea of clients, servers, and databases")

        emotional_context = ""
        frustration_topics = ["debug", "fix", "error", "broken", "migrate", "deploy"]
        if any(kw in topic_lower for kw in frustration_topics):
            emotional_context = "Reader may be stuck or frustrated mid-task. Prioritize working fixes and verification steps over background theory."

        audience_profile = AudienceProfile(
            reading_level=reading_level,
            assumed_knowledge=assumed_knowledge,
            emotional_context=emotional_context,
        )

        voice_profile = VoiceProfile(
            project_id=project_id,
            lexical_constraints=constraints,
            audience_profile=audience_profile,
            sample_conditioning=[],
            generic_phrase_blocklist=list(GLOBAL_GENERIC_PHRASES[:20]),
        )

        logger.info(
            "content_planner | project=%d | voice_profile built | constraints=%d | reading_level=%s",
            project_id, len(constraints), reading_level,
        )

        return voice_profile
