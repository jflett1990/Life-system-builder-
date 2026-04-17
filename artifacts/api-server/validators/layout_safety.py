"""
LayoutSafetyValidator — pre-render overflow check against the document manifest.

Phase A (current): runs in warning mode (BLOCKING_MODE=False).
  Logs overflow, orphan, and continuation issues against the layout report but
  does not block the render. Useful for observability while the manifest builder
  and height estimator stabilise on real production data.

Phase B (promotion): flip BLOCKING_MODE to True.
  Overflow errors then surface as hard failures and the render endpoint returns
  a 409 instead of a broken PDF. Safe to promote once the layout report shows a
  stable overflow rate < 2% across the last N production runs (PDR §11 SLO).

Callers can also override the module flag per-invocation via the `blocking=`
kwarg on validate_layout_safety().

The validator delegates to LayoutAnalyzer. This module is the pipeline
integration point — it owns the decision of whether to block or warn.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from render.layout_analyzer import LayoutAnalyzer, LayoutAnalysis
from render.manifest_builder import RenderManifest
from core.logging import get_logger

logger = get_logger(__name__)

# Flip to True to promote overflow warnings to hard errors (Phase B).
BLOCKING_MODE: bool = False


@dataclass
class LayoutSafetyResult:
    passed: bool
    analysis: LayoutAnalysis
    mode: str  # "warning" | "blocking"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "mode": self.mode,
            "analysis": self.analysis.to_dict(),
        }


def validate_layout_safety(
    manifest: RenderManifest,
    *,
    blocking: bool | None = None,
) -> LayoutSafetyResult:
    """Run the pre-render layout safety check.

    Args:
        manifest: The built RenderManifest to validate.
        blocking: Override the module-level BLOCKING_MODE when provided.
                  Pass True to enable Phase B hard-error behaviour.

    Returns:
        LayoutSafetyResult with passed=True when render should proceed.
    """
    is_blocking = blocking if blocking is not None else BLOCKING_MODE
    mode = "blocking" if is_blocking else "warning"

    analyzer = LayoutAnalyzer()
    analysis = analyzer.analyze(manifest, blocking=is_blocking)

    if analysis.errors:
        logger.error(
            "Layout safety: %d hard error(s) in manifest %s [mode=%s]: %s",
            len(analysis.errors),
            manifest.document_id,
            mode,
            "; ".join(analysis.errors[:5]),
        )
    if analysis.warnings:
        logger.warning(
            "Layout safety: %d warning(s) in manifest %s [mode=%s]",
            len(analysis.warnings),
            manifest.document_id,
            mode,
        )
    if analysis.overflow_pages:
        logger.warning(
            "Layout safety: overflow_risk on %d page(s): %s",
            len(analysis.overflow_pages),
            ", ".join(analysis.overflow_pages[:10]),
        )

    passed = analysis.passed if is_blocking else True
    return LayoutSafetyResult(passed=passed, analysis=analysis, mode=mode)
