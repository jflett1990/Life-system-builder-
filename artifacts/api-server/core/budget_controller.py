"""
BudgetController — model routing table, per-stage token envelopes, and spend telemetry.

Implements the PDR §07 cost controls:
  - Task type determines model tier; premium reserved for final prose synthesis only
  - Per-stage input/output token budgets with retry allowances
  - Structured spend telemetry events for the WebSocket dashboard (Phase D)

Model tiers:
  SMALL   — extraction, normalization (e.g. gpt-4o-mini or haiku)
  MID     — planning, structured extraction, outlines (e.g. gpt-4o or sonnet)
  PREMIUM — final narrative prose synthesis only (e.g. gpt-4o or claude-opus)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


# ── Model tiers ────────────────────────────────────────────────────────────────

class ModelTier(str, Enum):
    SMALL = "small"
    MID = "mid"
    PREMIUM = "premium"
    NONE = "none"  # deterministic stages — zero LLM cost


# ── Per-stage routing table (PDR §07) ─────────────────────────────────────────

STAGE_ROUTING: dict[str, ModelTier] = {
    # v2 stages
    "project_brief":        ModelTier.SMALL,
    "research_graph":       ModelTier.MID,
    "strategy_blueprint":   ModelTier.MID,
    "worksheet_transform":  ModelTier.NONE,
    "content_plan":         ModelTier.MID,
    "voice_profile":        ModelTier.MID,
    "chapter_outline":      ModelTier.MID,       # Pass A (outline)
    "chapter_prose":        ModelTier.PREMIUM,   # Pass B narrative blocks
    "chapter_structured":   ModelTier.MID,       # Pass B structured blocks
    "manifest_build":       ModelTier.NONE,
    "render":               ModelTier.NONE,
    "genericity_retry":     ModelTier.MID,

    # v1 legacy stages — mapped to mid tier (existing behaviour unchanged)
    "system_architecture":  ModelTier.MID,
    "document_outline":     ModelTier.MID,
    "chapter_expansion":    ModelTier.PREMIUM,   # narrative synthesis
    "chapter_worksheets":   ModelTier.MID,
    "appendix_builder":     ModelTier.MID,
    "layout_mapping":       ModelTier.MID,
    "render_blueprint":     ModelTier.MID,
    "validation_audit":     ModelTier.MID,
}


# ── Per-stage token budgets (PDR §07) ─────────────────────────────────────────

@dataclass(frozen=True)
class TokenBudget:
    input_tokens: int
    output_tokens: int
    retry_allowance: int  # additional retries beyond the base model retry


STAGE_BUDGETS: dict[str, TokenBudget] = {
    "project_brief":       TokenBudget(800,   400,  1),
    "research_graph":      TokenBudget(2000,  800,  1),
    "strategy_blueprint":  TokenBudget(3000,  1200, 1),
    "worksheet_transform": TokenBudget(0,     0,    0),
    "content_plan":        TokenBudget(2000,  1000, 1),
    "voice_profile":       TokenBudget(2000,  1000, 1),
    "chapter_outline":     TokenBudget(2500,  800,  2),  # per chapter
    "chapter_prose":       TokenBudget(1500,  600,  2),  # per section
    "manifest_build":      TokenBudget(0,     0,    0),
    "render":              TokenBudget(0,     0,    0),
}


# ── Spend event ───────────────────────────────────────────────────────────────

@dataclass
class SpendEvent:
    project_id: int
    stage: str
    model_tier: ModelTier
    model_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    was_retry: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "stage": self.stage,
            "model_tier": self.model_tier.value,
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "was_retry": self.was_retry,
            "timestamp": self.timestamp,
        }


# ── BudgetController ───────────────────────────────────────────────────────────

class BudgetController:
    """Resolve model assignments and track token spend per run.

    Usage:
        bc = BudgetController(project_id=42)
        model_id = bc.resolve_model(stage="chapter_prose")
        bc.record_spend(stage, model_id, input_tokens=1200, output_tokens=580)
        summary = bc.spend_summary()
    """

    def __init__(self, project_id: int) -> None:
        self._project_id = project_id
        self._events: list[SpendEvent] = []

    # ── Routing ────────────────────────────────────────────────────────────────

    def resolve_model(self, stage: str) -> str:
        """Return the model ID to use for this stage."""
        tier = STAGE_ROUTING.get(stage, ModelTier.MID)

        if tier == ModelTier.NONE:
            return "deterministic"

        if tier == ModelTier.SMALL:
            model = getattr(settings, "small_model", None) or getattr(settings, "executor_model", "gpt-4o-mini")
        elif tier == ModelTier.PREMIUM:
            model = getattr(settings, "premium_model", None) or getattr(settings, "executor_model", "gpt-4o")
        else:
            model = getattr(settings, "mid_model", None) or getattr(settings, "executor_model", "gpt-4o")

        return model

    def tier_for(self, stage: str) -> ModelTier:
        return STAGE_ROUTING.get(stage, ModelTier.MID)

    def budget_for(self, stage: str) -> TokenBudget | None:
        return STAGE_BUDGETS.get(stage)

    # ── Telemetry ──────────────────────────────────────────────────────────────

    def record_spend(
        self,
        stage: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        *,
        was_retry: bool = False,
    ) -> SpendEvent:
        event = SpendEvent(
            project_id=self._project_id,
            stage=stage,
            model_tier=self.tier_for(stage),
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            was_retry=was_retry,
        )
        self._events.append(event)
        record_project_spend(event)
        logger.debug(
            "Spend | project=%d | stage=%s | tier=%s | in=%d out=%d total=%d",
            self._project_id, stage, event.model_tier.value,
            input_tokens, output_tokens, event.total_tokens,
        )
        return event

    def spend_summary(self) -> dict[str, Any]:
        total_tokens = sum(e.total_tokens for e in self._events)
        premium_tokens = sum(e.total_tokens for e in self._events if e.model_tier == ModelTier.PREMIUM)
        mid_tokens = sum(e.total_tokens for e in self._events if e.model_tier == ModelTier.MID)
        small_tokens = sum(e.total_tokens for e in self._events if e.model_tier == ModelTier.SMALL)
        retry_count = sum(1 for e in self._events if e.was_retry)
        stages_run = list({e.stage for e in self._events})

        return {
            "project_id": self._project_id,
            "total_tokens": total_tokens,
            "premium_tokens": premium_tokens,
            "mid_tokens": mid_tokens,
            "small_tokens": small_tokens,
            "retry_count": retry_count,
            "stages_run": stages_run,
            "event_count": len(self._events),
        }

    def events(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._events]


# ── Module-level project-scoped spend registry (PDR §09 dashboard) ─────────────
#
# BudgetController instances are transient (one per stage run). To expose cost
# observability via /api/telemetry/spend/{project_id}, each recorded event also
# appends to this process-wide registry keyed by project_id.

_SPEND_REGISTRY: dict[int, list[SpendEvent]] = {}


def record_project_spend(event: SpendEvent) -> None:
    """Append a spend event to the module-level registry."""
    _SPEND_REGISTRY.setdefault(event.project_id, []).append(event)


def project_spend_events(project_id: int) -> list[SpendEvent]:
    return list(_SPEND_REGISTRY.get(project_id, []))


def project_spend_summary(project_id: int) -> dict[str, Any]:
    events = _SPEND_REGISTRY.get(project_id, [])
    total_tokens = sum(e.total_tokens for e in events)
    per_stage: dict[str, dict[str, int]] = {}
    for e in events:
        bucket = per_stage.setdefault(e.stage, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        bucket["calls"] += 1
        bucket["input_tokens"] += e.input_tokens
        bucket["output_tokens"] += e.output_tokens
        bucket["total_tokens"] += e.total_tokens

    return {
        "project_id": project_id,
        "event_count": len(events),
        "total_tokens": total_tokens,
        "premium_tokens": sum(e.total_tokens for e in events if e.model_tier == ModelTier.PREMIUM),
        "mid_tokens": sum(e.total_tokens for e in events if e.model_tier == ModelTier.MID),
        "small_tokens": sum(e.total_tokens for e in events if e.model_tier == ModelTier.SMALL),
        "retry_count": sum(1 for e in events if e.was_retry),
        "per_stage": per_stage,
    }


def clear_project_spend(project_id: int) -> None:
    _SPEND_REGISTRY.pop(project_id, None)
