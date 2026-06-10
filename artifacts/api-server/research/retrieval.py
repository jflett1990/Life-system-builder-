"""
Retrieval — knowledge retrieval for the research graph.

Primary path (tutorial builder):
  Firecrawl web search + scrape when FIRECRAWL_API_KEY is configured.

Fallback path:
  Built-in snippet library (legacy stub — used only when Firecrawl is unavailable).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievedPassage:
    passage_id: str
    text: str
    source: str
    source_type: str          # official_docs | web | government | legal | general
    jurisdiction_tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0


# Legacy snippet library — fallback only when Firecrawl is not configured.
_SNIPPET_LIBRARY: list[dict[str, Any]] = [
    {
        "text": "When starting a new web project, pin dependency versions in package.json or requirements.txt to avoid breaking changes from upstream releases.",
        "source": "General Software Engineering Practice",
        "source_type": "general",
        "jurisdiction_tags": ["coding", "tutorial"],
        "keywords": ["dependencies", "version", "package", "setup"],
    },
    {
        "text": "Environment variables for API keys and secrets should never be committed to version control. Use a .env file locally and platform secret managers in production.",
        "source": "Security Best Practices",
        "source_type": "general",
        "jurisdiction_tags": ["coding", "security"],
        "keywords": ["environment", "secrets", "api key", "env"],
    },
]


def _score_passage(passage: dict[str, Any], keywords: list[str], jurisdiction: str | None) -> float:
    score = 0.0
    text_lower = (passage["text"] + " " + " ".join(passage.get("keywords", []))).lower()

    for kw in keywords:
        kw_lower = kw.lower().strip()
        if kw_lower and kw_lower in text_lower:
            score += 1.0 / (1 + text_lower.index(kw_lower) / max(len(text_lower), 1))

    if jurisdiction:
        jur_lower = jurisdiction.lower()
        tags = [t.lower() for t in passage.get("jurisdiction_tags", [])]
        if any(jur_lower in tag for tag in tags):
            score += 0.5

    return score


def _retrieve_from_snippet_library(
    query_keywords: list[str],
    jurisdiction: str | None,
    life_event: str,
    max_results: int,
) -> list[RetrievedPassage]:
    all_keywords = list(query_keywords)
    if life_event:
        words = re.findall(r"\b\w{4,}\b", life_event.lower())
        all_keywords.extend(words[:10])

    scored: list[tuple[float, dict[str, Any]]] = []
    for snippet in _SNIPPET_LIBRARY:
        score = _score_passage(snippet, all_keywords, jurisdiction)
        if score > 0:
            scored.append((score, snippet))

    scored.sort(key=lambda x: x[0], reverse=True)

    passages: list[RetrievedPassage] = []
    for i, (score, snippet) in enumerate(scored[:max_results]):
        passages.append(RetrievedPassage(
            passage_id=f"p{i+1:03d}",
            text=snippet["text"],
            source=snippet["source"],
            source_type=snippet["source_type"],
            jurisdiction_tags=snippet.get("jurisdiction_tags", []),
            relevance_score=round(score, 3),
        ))
    return passages


def _retrieve_from_firecrawl(brief: dict[str, Any]) -> list[RetrievedPassage]:
    from research.firecrawl_client import FirecrawlError, research_tutorial_via_firecrawl

    try:
        raw_passages = research_tutorial_via_firecrawl(brief)
    except FirecrawlError as exc:
        logger.warning("firecrawl retrieval unavailable: %s", exc)
        return []

    return [
        RetrievedPassage(
            passage_id=p["passage_id"],
            text=p["text"],
            source=p["source"],
            source_type=p["source_type"],
            jurisdiction_tags=p.get("jurisdiction_tags", []),
            relevance_score=p.get("relevance_score", 0.0),
        )
        for p in raw_passages
    ]


def _parse_stack_from_context(context: str | None) -> str:
    if not context:
        return ""
    for line in context.splitlines():
        lower = line.lower()
        if "stack" in lower or "framework" in lower or "language" in lower:
            _, _, value = line.partition(":")
            return value.strip()
    return ""


def retrieve_passages(
    query_keywords: list[str],
    jurisdiction: str | None = None,
    life_event: str = "",
    max_results: int = 12,
    *,
    brief: dict[str, Any] | None = None,
) -> list[RetrievedPassage]:
    """Retrieve relevant passages for tutorial research.

    Uses Firecrawl when configured; falls back to the built-in snippet library.
    """
    enriched_brief = dict(brief or {})
    if life_event and not enriched_brief.get("life_event"):
        enriched_brief["life_event"] = life_event
    if jurisdiction and not enriched_brief.get("jurisdiction"):
        enriched_brief["jurisdiction"] = jurisdiction
    if not enriched_brief.get("stack"):
        enriched_brief["stack"] = _parse_stack_from_context(enriched_brief.get("context"))

    passages: list[RetrievedPassage] = []

    if settings.get_firecrawl_api_key():
        passages = _retrieve_from_firecrawl(enriched_brief)
        if passages:
            logger.info("retrieval | firecrawl returned %d passages", len(passages))
            return passages[:max_results]
        logger.warning("retrieval | firecrawl returned no passages — using fallback library")

    return _retrieve_from_snippet_library(query_keywords, jurisdiction, life_event, max_results)
