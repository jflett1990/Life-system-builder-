"""
StrategyBuilder — Stage 2: Strategy Blueprint generation.

PDR §04 Stage 2:
  Converts project_brief + research_graph into the strategy blueprint.
  This is the single source of truth for domains, roles, milestones,
  risk gates, and worksheet seeds.

  In Phase C: the blueprint is derived deterministically from the
  research graph coverage map and the project brief entities.
  A mid-tier LLM call enriches domain goals and operating principles
  (passed in as model_output when called from the pipeline stage).

  worksheet_seeds are emitted so Stage 2.5 can generate worksheet
  packets without any further LLM calls.
"""
from __future__ import annotations

import re
from typing import Any

from core.logging import get_logger
from models.v2_artifacts import (
    StrategyBlueprint,
    DomainModel,
    MilestoneModel,
    RiskGate,
    WorksheetSeed,
)

logger = get_logger(__name__)


# ── Module detection from tutorial topic ──────────────────────────────────────

TOPIC_DOMAINS: dict[str, list[str]] = {
    "web_app": [
        "Project Scaffold & Tooling Setup",
        "Core UI & Page Structure",
        "Data Layer & API Wiring",
        "Interactivity & State",
        "Testing & Verification",
        "Build & Deployment",
    ],
    "api_backend": [
        "Environment & Project Setup",
        "Data Model & Persistence",
        "Endpoints & Business Logic",
        "Auth & Validation",
        "Testing & Error Handling",
        "Deployment & Monitoring",
    ],
    "bot_automation": [
        "Platform Account & Token Setup",
        "Bot Scaffold & Connection",
        "Command & Event Handling",
        "State & Persistence",
        "Testing in a Sandbox",
        "Hosting & Keep-Alive",
    ],
    "deployment": [
        "Pre-Deploy Audit & Configuration",
        "Containerisation / Packaging",
        "Platform Setup & Secrets",
        "First Deploy & Smoke Test",
        "Custom Domains & TLS",
        "Monitoring & Rollback",
    ],
    "data_ai": [
        "Environment & Dependency Setup",
        "Data / Model Acquisition",
        "Core Pipeline Implementation",
        "Evaluation & Iteration",
        "Interface & Integration",
        "Packaging & Sharing",
    ],
    "default": [
        "Setup & Prerequisites",
        "Core Build",
        "Integration & Wiring",
        "Verification & Debugging",
        "Polish & Edge Cases",
        "Ship & Next Steps",
    ],
}

# Backwards-compatible alias (pre-pivot name)
LIFE_EVENT_DOMAINS = TOPIC_DOMAINS


def _detect_topic_type(topic: str) -> str:
    topic_lower = topic.lower()
    if any(kw in topic_lower for kw in ["deploy", "ship", "hosting", "docker", "kubernetes", "ci/cd", "devops"]):
        return "deployment"
    if any(kw in topic_lower for kw in ["bot", "automation", "scraper", "cron", "webhook", "discord", "slack", "telegram"]):
        return "bot_automation"
    if any(kw in topic_lower for kw in ["api", "backend", "server", "fastapi", "express", "database", "crud", "rest", "graphql"]):
        return "api_backend"
    if any(kw in topic_lower for kw in ["ai", "ml", "model", "llm", "data science", "machine learning", "chatbot", "rag"]):
        return "data_ai"
    if any(kw in topic_lower for kw in ["app", "website", "site", "frontend", "react", "next", "vue", "landing", "page", "extension", "ui"]):
        return "web_app"
    return "default"


# Backwards-compatible alias (pre-pivot name)
_detect_event_type = _detect_topic_type


def _build_domain_id(name: str, idx: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"d{idx+1:02d}_{slug[:20]}"


# ── StrategyBuilder ────────────────────────────────────────────────────────────

class StrategyBuilder:
    """Builds a StrategyBlueprint from project brief and research graph.

    Phase C: deterministic domain scaffolding + research-grounded enrichment.
    Model output (from a mid-tier LLM call in the pipeline stage) can be
    passed to ``enrich_from_model_output`` to add goals and principles.
    """

    def build(
        self,
        project_id: int,
        brief: dict[str, Any],
        research_graph: dict[str, Any],
        *,
        model_output: dict[str, Any] | None = None,
    ) -> StrategyBlueprint:
        topic = brief.get("topic_type", "") or brief.get("topic", "")
        topic_type = _detect_topic_type(topic)
        domain_names = TOPIC_DOMAINS.get(topic_type, TOPIC_DOMAINS["default"])

        # Build domain models
        domains: list[DomainModel] = []
        for i, name in enumerate(domain_names):
            domain_id = _build_domain_id(name, i)
            goals, principles, roles = self._enrich_domain(
                domain_id, name, model_output, brief, research_graph
            )
            domains.append(DomainModel(
                domain_id=domain_id,
                name=name,
                goals=goals,
                operating_principles=principles,
                role_assignments=roles,
            ))

        # Build milestones from brief deadlines + research facts
        milestones = self._build_milestones(brief, domains)

        # Build risk gates from research conflict flags + high-stakes domains
        risk_gates = self._build_risk_gates(domains, research_graph)

        # Emit worksheet seeds (consumed by Stage 2.5)
        worksheet_seeds = self._build_worksheet_seeds(domains, milestones, risk_gates)

        blueprint = StrategyBlueprint(
            project_id=project_id,
            domains=domains,
            milestones=milestones,
            risk_gates=risk_gates,
            worksheet_seeds=worksheet_seeds,
        )

        logger.info(
            "strategy_builder | project=%d | domains=%d | milestones=%d | "
            "risk_gates=%d | worksheet_seeds=%d",
            project_id, len(domains), len(milestones),
            len(risk_gates), len(worksheet_seeds),
        )
        return blueprint

    # ── Internal builders ──────────────────────────────────────────────────────

    def _enrich_domain(
        self,
        domain_id: str,
        domain_name: str,
        model_output: dict[str, Any] | None,
        brief: dict[str, Any],
        research_graph: dict[str, Any],
    ) -> tuple[list[str], list[str], dict[str, str]]:
        """Return (goals, principles, role_assignments) for a domain."""
        goals: list[str] = []
        principles: list[str] = []
        roles: dict[str, str] = {}

        # Pull from LLM model output if available
        if model_output:
            for d in model_output.get("domains", []):
                if d.get("domain_id") == domain_id or d.get("name", "").lower() == domain_name.lower():
                    goals = d.get("goals", [])
                    principles = d.get("operating_principles", [])
                    roles = d.get("role_assignments", {})
                    break

        # Fill from brief if still empty
        if not goals:
            goals = [f"Manage all {domain_name.lower()} activities effectively"]
        if not principles:
            principles = ["Act on verified information only", "Document all decisions"]

        # Assign known roles from brief
        if not roles:
            for person in brief.get("people", []):
                role = person.get("role", "")
                name = person.get("name", "")
                if role and name:
                    roles[role] = name

        return goals, principles, roles

    def _build_milestones(
        self,
        brief: dict[str, Any],
        domains: list[DomainModel],
    ) -> list[MilestoneModel]:
        milestones: list[MilestoneModel] = []

        for i, deadline in enumerate(brief.get("deadlines", [])):
            responsible = next(
                (p.get("role", "Responsible party") for p in brief.get("people", [])
                 if p.get("role")), "Project lead"
            )
            milestones.append(MilestoneModel(
                milestone_id=f"m{i+1:02d}",
                label=deadline.get("label", f"Deadline {i+1}"),
                deadline_description=deadline.get("date_description", ""),
                responsible_role=responsible,
                dependencies=[],
            ))

        # Add a completion milestone per domain
        for i, domain in enumerate(domains[:4]):
            milestones.append(MilestoneModel(
                milestone_id=f"md{i+1:02d}",
                label=f"Complete {domain.name}",
                deadline_description="To be determined",
                responsible_role=next(iter(domain.role_assignments.values()), "Project lead"),
                dependencies=[],
            ))

        return milestones

    def _build_risk_gates(
        self,
        domains: list[DomainModel],
        research_graph: dict[str, Any],
    ) -> list[RiskGate]:
        gates: list[RiskGate] = []
        conflicting_facts = [
            f for f in research_graph.get("facts", [])
            if f.get("conflict_flags")
        ]
        for i, fact in enumerate(conflicting_facts[:5]):
            gates.append(RiskGate(
                gate_id=f"rg{i+1:02d}",
                condition=f"Conflicting guidance detected: {fact.get('claim', '')[:80]}",
                cascade_triggers=["Pause all related actions", "Seek professional clarification"],
                escalation_path="Legal or financial professional consultation required",
            ))

        # Add standard high-stakes gates for first two domains
        for i, domain in enumerate(domains[:2]):
            gates.append(RiskGate(
                gate_id=f"rgd{i+1:02d}",
                condition=f"{domain.name} milestone missed or blocked",
                cascade_triggers=["Notify all role assignments", "Re-evaluate timeline"],
                escalation_path="Project lead escalation",
            ))

        return gates

    def _build_worksheet_seeds(
        self,
        domains: list[DomainModel],
        milestones: list[MilestoneModel],
        risk_gates: list[RiskGate],
    ) -> list[WorksheetSeed]:
        seeds: list[WorksheetSeed] = []
        milestone_ids = [m.milestone_id for m in milestones]
        gate_ids = [g.gate_id for g in risk_gates]

        # One contact sheet per project
        seeds.append(WorksheetSeed(
            seed_id="ws-contacts",
            worksheet_type="contact_sheet",
            domain_id=domains[0].domain_id if domains else "d01",
            title="Key Contacts & Roles",
            source_entities=[p for d in domains for p in d.role_assignments.keys()],
        ))

        # Timeline tracker anchored to milestones
        seeds.append(WorksheetSeed(
            seed_id="ws-timeline",
            worksheet_type="timeline_tracker",
            domain_id=domains[0].domain_id if domains else "d01",
            title="Project Timeline & Milestones",
            source_milestones=milestone_ids,
        ))

        # Escalation matrix from risk gates
        if risk_gates:
            seeds.append(WorksheetSeed(
                seed_id="ws-escalation",
                worksheet_type="escalation_matrix",
                domain_id=domains[0].domain_id if domains else "d01",
                title="Escalation Matrix",
                source_risk_gates=gate_ids,
            ))

        # Task tracker per domain (first 3 domains)
        for domain in domains[:3]:
            seeds.append(WorksheetSeed(
                seed_id=f"ws-tasks-{domain.domain_id}",
                worksheet_type="task_tracker",
                domain_id=domain.domain_id,
                title=f"{domain.name} — Task Tracker",
            ))

        return seeds
