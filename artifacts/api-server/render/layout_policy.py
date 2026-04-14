"""
Layout policy orchestration for RenderManifest pages.

This layer normalises page-model behaviour before HTML emission so pagination
is not driven only by CSS heuristics.  It applies three controls:

1) Page model contract (fixed | flow | full_bleed)
2) Explicit page-boundary markers (break-before classes)
3) Duplicate-page guardrails (same conceptual payload emitted twice)
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any
import json


_FULL_BLEED_ARCHETYPES = {"cover_page", "section_divider"}
_FIXED_ARCHETYPES = {
    "toc_page",
    "dashboard_page",
    "chapter_opener",
    "reference_card_page",
    "rapid_response",
}


@dataclass(frozen=True)
class LayoutPolicy:
    model: str  # "fixed" | "flow" | "full_bleed"
    force_break_before: bool
    block_policy: str  # "atomic" | "splittable" | "page_forcing"


def _stable_payload_signature(data: dict[str, Any]) -> str:
    """Return a deterministic digest for dedupe guardrails."""
    try:
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        raw = repr(data)
    return sha1(raw.encode("utf-8")).hexdigest()


class LayoutOrchestrator:
    """
    Applies explicit layout policy and guards against duplicate page emission.
    """

    def classify_page(self, page: Any, is_first: bool = False) -> LayoutPolicy:
        archetype = getattr(page, "archetype", "")
        page_break = getattr(page, "page_break", "always")

        if archetype in _FULL_BLEED_ARCHETYPES:
            return LayoutPolicy(
                model="full_bleed",
                force_break_before=True,
                block_policy="page_forcing",
            )
        if page_break == "always" or archetype in _FIXED_ARCHETYPES:
            return LayoutPolicy(
                model="fixed",
                force_break_before=not is_first,
                block_policy="page_forcing",
            )
        return LayoutPolicy(
            model="flow",
            force_break_before=False,
            block_policy="splittable",
        )

    def orchestrate(self, pages: list[Any]) -> list[Any]:
        out: list[Any] = []
        seen_signatures: set[tuple[str, str]] = set()

        for idx, page in enumerate(pages):
            policy = self.classify_page(page, is_first=(idx == 0))

            # Duplicate guardrail: skip exact duplicate payload for the same archetype.
            # We keep the first emission and drop accidental repeats.
            signature = (page.archetype, _stable_payload_signature(page.data))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)

            page.layout_mode = policy.model
            page.break_before = policy.force_break_before
            page.block_policy = policy.block_policy
            out.append(page)

        return out

