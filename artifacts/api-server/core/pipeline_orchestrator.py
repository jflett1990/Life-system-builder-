"""
PipelineOrchestrator — enforces stage sequencing and upstream dependency resolution.
Services call this to get upstream outputs before running a stage.
"""
from __future__ import annotations

from typing import Any

from core.logging import get_logger
from schemas.stage import STAGE_NAMES, STAGE_ORDER

logger = get_logger(__name__)


class PipelineError(Exception):
    """Raised when a pipeline constraint is violated."""


STAGE_CONTRACT_MAP: dict[str, str] = {
    "system_architecture": "life_event_system_core",
    "document_outline":    "document_outline",
    "chapter_expansion":   "chapter_expansion",
    "appendix_builder":    "appendix_builder",
    "layout_mapping":      "layout_architecture_mapper",
    "render_blueprint":    "pdf_render_blueprint",
    "validation_audit":    "life_system_validation_agent",
}

STAGE_UPSTREAM_MAP: dict[str, list[str]] = {
    "system_architecture": [],
    "document_outline":    ["system_architecture"],
    "chapter_expansion":   ["system_architecture", "document_outline"],
    "appendix_builder":    ["system_architecture", "document_outline", "chapter_expansion"],
    "layout_mapping":      ["system_architecture", "document_outline", "chapter_expansion"],
    "render_blueprint":    ["system_architecture", "document_outline", "chapter_expansion", "layout_mapping"],
    "validation_audit":    ["system_architecture", "document_outline", "chapter_expansion", "appendix_builder", "layout_mapping", "render_blueprint"],
}


class PipelineOrchestrator:
    def resolve_contract_name(self, stage: str) -> str:
        if stage not in STAGE_CONTRACT_MAP:
            raise PipelineError(
                f"Unknown stage '{stage}'. Valid stages: {STAGE_NAMES}"
            )
        return STAGE_CONTRACT_MAP[stage]

    def upstream_stages(self, stage: str) -> list[str]:
        if stage not in STAGE_UPSTREAM_MAP:
            raise PipelineError(f"Unknown stage '{stage}'")
        return STAGE_UPSTREAM_MAP[stage]

    def check_upstream_complete(
        self, stage: str, completed_stages: set[str]
    ) -> None:
        """Raise if required upstream stages are not complete."""
        required = self.upstream_stages(stage)
        missing = [s for s in required if s not in completed_stages]
        if missing:
            raise PipelineError(
                f"Stage '{stage}' requires upstream stages to be complete first: "
                + ", ".join(missing)
            )

    def collect_upstream_outputs(
        self,
        stage: str,
        all_stage_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Return only the upstream outputs this stage depends on."""
        return {
            s: all_stage_outputs[s]
            for s in self.upstream_stages(stage)
            if s in all_stage_outputs
        }

    def next_runnable_stage(self, completed_stages: set[str]) -> str | None:
        """Return the next stage that can be run given completed stages."""
        for stage in STAGE_NAMES:
            if stage in completed_stages:
                continue
            required = self.upstream_stages(stage)
            if all(r in completed_stages for r in required):
                return stage
        return None

    def pipeline_progress(self, completed_stages: set[str]) -> dict:
        return {
            "total": len(STAGE_NAMES),
            "completed": len(completed_stages & set(STAGE_NAMES)),
            "remaining": [s for s in STAGE_NAMES if s not in completed_stages],
            "next": self.next_runnable_stage(completed_stages),
        }
