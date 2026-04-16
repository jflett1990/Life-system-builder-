"""
v2 Pipeline Artifact Schemas — Pydantic models for all IR types defined in PDR §05.

Each artifact carries a schema_version field. Artifacts are immutable on write;
downstream stages consume them as typed data contracts, not raw prose.

Artifacts defined here:
  - ProjectBrief          (Stage 0 output)
  - ResearchGraph         (Stage 1 output)
  - StrategyBlueprint     (Stage 2 output)
  - WorksheetPacket       (Stage 2.5 output)
  - ContentPlan           (Stage 3 output)
  - VoiceProfile          (Stage 3 output)
  - ChapterPacket         (Stage 4 output)
  - DocumentManifestMeta  (Stage 5 output — lightweight metadata only)
  - LayoutReportArtifact  (Stage 5 output — layout_report.json)
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Shared primitives ──────────────────────────────────────────────────────────

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BlockType(str, Enum):
    NARRATIVE = "narrative"
    CALLOUT = "callout"
    TABLE = "table"
    WORKSHEET_REF = "worksheet_ref"
    LIST = "list"
    HEADING = "heading"


# ── Stage 0: Project Brief ─────────────────────────────────────────────────────

class PersonEntity(BaseModel):
    name: str
    role: str
    contact: str | None = None


class DeadlineEntity(BaseModel):
    label: str
    deadline_type: str
    date_description: str
    is_critical: bool = False


class ProjectBrief(BaseModel):
    schema_version: str = "1.0"
    project_id: int
    life_event_type: str
    life_event_subtype: str | None = None
    people: list[PersonEntity] = Field(default_factory=list)
    deadlines: list[DeadlineEntity] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    jurisdiction: str | None = None
    jurisdiction_tags: list[str] = Field(default_factory=list)
    locale: str = "en-US"
    constraints: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    raw_intake: dict[str, Any] = Field(default_factory=dict)


# ── Stage 1: Research Graph ────────────────────────────────────────────────────

class ResearchFact(BaseModel):
    fact_id: str
    claim: str
    source: str
    confidence: ConfidenceLevel
    jurisdiction_tags: list[str] = Field(default_factory=list)
    conflict_flags: list[str] = Field(default_factory=list)


class CoverageMapEntry(BaseModel):
    entity: str
    entity_type: str
    covered: bool
    fact_ids: list[str] = Field(default_factory=list)


class ResearchGraph(BaseModel):
    schema_version: str = "1.0"
    project_id: int
    facts: list[ResearchFact] = Field(default_factory=list)
    coverage_map: list[CoverageMapEntry] = Field(default_factory=list)
    total_facts: int = 0
    low_confidence_count: int = 0
    conflict_count: int = 0
    critical_coverage_met: bool = True


# ── Stage 2: Strategy Blueprint ───────────────────────────────────────────────

class DomainModel(BaseModel):
    domain_id: str
    name: str
    goals: list[str] = Field(default_factory=list)
    operating_principles: list[str] = Field(default_factory=list)
    role_assignments: dict[str, str] = Field(default_factory=dict)


class MilestoneModel(BaseModel):
    milestone_id: str
    label: str
    deadline_description: str
    responsible_role: str
    dependencies: list[str] = Field(default_factory=list)


class RiskGate(BaseModel):
    gate_id: str
    condition: str
    cascade_triggers: list[str] = Field(default_factory=list)
    escalation_path: str = ""


class WorksheetSeed(BaseModel):
    seed_id: str
    worksheet_type: str
    domain_id: str
    title: str
    source_entities: list[str] = Field(default_factory=list)
    source_milestones: list[str] = Field(default_factory=list)
    source_risk_gates: list[str] = Field(default_factory=list)


class StrategyBlueprint(BaseModel):
    schema_version: str = "1.0"
    project_id: int
    domains: list[DomainModel] = Field(default_factory=list)
    milestones: list[MilestoneModel] = Field(default_factory=list)
    risk_gates: list[RiskGate] = Field(default_factory=list)
    worksheet_seeds: list[WorksheetSeed] = Field(default_factory=list)


# ── Stage 2.5: Worksheet Packets (deterministic — zero LLM) ───────────────────

class ColumnDefinition(BaseModel):
    name: str
    col_type: str  # text | yn_circle | date | owner_select | status_badge
    width_hint: str | None = None


class WorksheetRow(BaseModel):
    row_id: str
    cells: dict[str, Any] = Field(default_factory=dict)
    is_prefilled: bool = False


class WorksheetPacket(BaseModel):
    schema_version: str = "1.0"
    worksheet_id: str
    worksheet_type: str
    domain_id: str
    title: str
    purpose: str = ""
    columns: list[ColumnDefinition] = Field(default_factory=list)
    rows: list[WorksheetRow] = Field(default_factory=list)
    instructions_block: str | None = None  # only LLM-generated element if present


# ── Stage 3: Content Plan ──────────────────────────────────────────────────────

class ComponentChoice(BaseModel):
    component_type: BlockType
    required: bool = True
    citation_quota: int = 0


class ChapterMapEntry(BaseModel):
    chapter_id: str
    domain_id: str
    title: str
    depth_target: int = 1
    depth_weight: float = 1.0  # 0.5–2.0 multiplier (adaptive depth engine)
    required_components: list[ComponentChoice] = Field(default_factory=list)
    citation_quota: int = 0


class ContentPlan(BaseModel):
    schema_version: str = "1.0"
    project_id: int
    chapter_map: list[ChapterMapEntry] = Field(default_factory=list)
    component_choices: list[ComponentChoice] = Field(default_factory=list)


# ── Stage 3: Voice Profile ────────────────────────────────────────────────────

class LexicalConstraint(BaseModel):
    constraint_type: str  # banned_phrase | required_term | tone_descriptor
    value: str
    reason: str = ""


class AudienceProfile(BaseModel):
    reading_level: str = "general"
    assumed_knowledge: list[str] = Field(default_factory=list)
    emotional_context: str = ""


class VoiceProfile(BaseModel):
    schema_version: str = "1.0"
    project_id: int
    lexical_constraints: list[LexicalConstraint] = Field(default_factory=list)
    audience_profile: AudienceProfile = Field(default_factory=AudienceProfile)
    sample_conditioning: list[str] = Field(default_factory=list)
    generic_phrase_blocklist: list[str] = Field(default_factory=list)


# ── Stage 4: Chapter Packets ───────────────────────────────────────────────────

class ContentBlock(BaseModel):
    block_id: str
    block_type: BlockType
    content: str
    fact_ids: list[str] = Field(default_factory=list)
    rewrite_rationale: str | None = None


class ChapterPacket(BaseModel):
    schema_version: str = "1.0"
    chapter_id: str
    project_id: int
    domain_id: str
    title: str
    blocks: list[ContentBlock] = Field(default_factory=list)
    citation_coverage_score: float = 0.0
    pass_a_outline_validated: bool = False
    pass_b_prose_validated: bool = False
    genericity_guard_passed: bool = False


# ── Stage 5: Document Manifest Metadata ───────────────────────────────────────

class DocumentManifestMeta(BaseModel):
    schema_version: str = "1.0"
    project_id: int
    document_id: str
    total_pages: int
    overflow_risk_pages: list[str] = Field(default_factory=list)
    continuation_splits: int = 0


# ── Stage 5: Layout Report Artifact ──────────────────────────────────────────

class SplitEvent(BaseModel):
    block_id: str
    block_type: str
    page: int
    reason: str
    continuation_page: int


class LayoutReportArtifact(BaseModel):
    schema_version: str = "1.0"
    project_id: int
    document_id: str
    total_pages: int
    overflow_risk_count: int
    split_events: list[SplitEvent] = Field(default_factory=list)
    orphan_warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
