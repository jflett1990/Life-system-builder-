"""
LayoutAnalyzer — pre-render validation chain for the document manifest.

Implements the PDR §08 validation chain:
  1. Walk all pages for overflow_risk blocks
  2. Orphan detector: headings within 60 px of page bottom
  3. Continuation integrity: blocks marked continuation_of have valid parent IDs
  4. Hard errors hold render; warnings proceed

Returns a LayoutAnalysis with hard errors, warnings, and a pass/hold decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from render.manifest_builder import RenderManifest, ManifestPage
from render.height_estimator import EFFECTIVE_ZONE_PX


ORPHAN_THRESHOLD_PX: int = 60


@dataclass
class LayoutAnalysis:
    """Result of the pre-render layout validation chain."""
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    overflow_pages: list[str] = field(default_factory=list)
    orphan_candidates: list[str] = field(default_factory=list)
    continuation_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "overflow_pages": self.overflow_pages,
            "orphan_candidates": self.orphan_candidates,
            "continuation_errors": self.continuation_errors,
        }


class LayoutAnalyzer:
    """Pre-render manifest validator.

    Usage:
        analyzer = LayoutAnalyzer()
        analysis = analyzer.analyze(manifest)
        if not analysis.passed:
            # Hold render; surface layout_report
    """

    def analyze(self, manifest: RenderManifest, *, blocking: bool = False) -> LayoutAnalysis:
        """Run the full validation chain against a built manifest.

        Args:
            manifest: The RenderManifest to validate.
            blocking: When True, overflow_risk pages become hard errors (Phase B).
                      When False (Phase A default), they produce warnings only.
        """
        errors: list[str] = []
        warnings: list[str] = []
        overflow_pages: list[str] = []
        orphan_candidates: list[str] = []
        continuation_errors: list[str] = []

        all_page_ids = {p.page_id for p in manifest.pages}

        for page in manifest.pages:
            self._check_overflow(
                page, errors, warnings, overflow_pages, blocking=blocking
            )
            self._check_orphan(page, orphan_candidates, warnings)
            self._check_continuation(page, all_page_ids, continuation_errors, errors)

        passed = len(errors) == 0
        return LayoutAnalysis(
            passed=passed,
            errors=errors,
            warnings=warnings,
            overflow_pages=overflow_pages,
            orphan_candidates=orphan_candidates,
            continuation_errors=continuation_errors,
        )

    # ── Check implementations ──────────────────────────────────────────────────

    def _check_overflow(
        self,
        page: ManifestPage,
        errors: list[str],
        warnings: list[str],
        overflow_pages: list[str],
        *,
        blocking: bool,
    ) -> None:
        if not page.overflow_risk:
            return
        overflow_pages.append(page.page_id)
        msg = (
            f"[overflow] {page.page_id} (archetype={page.archetype}): "
            f"estimated {page.estimated_height_px}px exceeds zone budget "
            f"{page.zone_budget_px}px"
        )
        if blocking:
            errors.append(msg)
        else:
            warnings.append(msg)

    def _check_orphan(
        self,
        page: ManifestPage,
        orphan_candidates: list[str],
        warnings: list[str],
    ) -> None:
        """Flag heading archetypes where remaining space after content is < ORPHAN_THRESHOLD_PX."""
        if page.archetype not in ("chapter_opener", "explanation_page", "reference_card_page"):
            return
        remaining = page.zone_budget_px - page.estimated_height_px
        if 0 < remaining < ORPHAN_THRESHOLD_PX:
            candidate = page.page_id
            orphan_candidates.append(candidate)
            warnings.append(
                f"[orphan] {candidate}: only {remaining}px remaining — "
                "heading may be orphaned at page bottom"
            )

    def _check_continuation(
        self,
        page: ManifestPage,
        all_page_ids: set[str],
        continuation_errors: list[str],
        errors: list[str],
    ) -> None:
        """Validate that continuation_of references point to existing page IDs."""
        for block in page.blocks:
            if block.continuation and block.continuation_of:
                if block.continuation_of not in all_page_ids:
                    msg = (
                        f"[continuation] block {block.block_id} on page {page.page_id} "
                        f"references missing parent '{block.continuation_of}'"
                    )
                    continuation_errors.append(msg)
                    errors.append(msg)
