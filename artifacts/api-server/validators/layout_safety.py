"""
LayoutSafetyValidator — pre-render overflow check against the document manifest.

Phase A: runs in warning mode (blocking=False). Logs issues but does not halt render.
Phase B: promoted to blocking mode (blocking=True). Holds render on hard errors.

The validator delegates to LayoutAnalyzer. This module is the pipeline integration
point — it owns the decision of whether to block or warn.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from render.layout_analyzer import LayoutAnalyzer, LayoutAnalysis
from render.manifest_builder import RenderManifest
from core.logging import get_logger

logger = get_logger(__name__)

# Set to True in Phase B to promote overflow warnings to hard errors.
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
