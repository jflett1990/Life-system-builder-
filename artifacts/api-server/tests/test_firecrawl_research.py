"""Tests for Firecrawl-backed tutorial research."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from research.firecrawl_client import (
    FirecrawlError,
    FirecrawlSearchResult,
    build_tutorial_search_queries,
    research_tutorial_via_firecrawl,
)
from research.retrieval import retrieve_passages


def test_build_tutorial_search_queries_includes_stack() -> None:
    brief = {
        "life_event": "Build a SaaS landing page with Next.js",
        "stack": "Next.js 14, TypeScript, Tailwind",
        "platform": "Vercel",
        "tutorial_type": "hands-on build",
        "systems": ["App Router Setup", "Tailwind Configuration"],
    }
    queries = build_tutorial_search_queries(brief)
    assert any("Next.js" in q for q in queries)
    assert any("documentation" in q.lower() or "tutorial" in q.lower() for q in queries)
    assert len(queries) >= 2


@patch("research.firecrawl_client.FirecrawlClient")
def test_research_tutorial_via_firecrawl_scrapes_results(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.search.return_value = [
        FirecrawlSearchResult(
            url="https://nextjs.org/docs",
            title="Next.js Docs",
            description="Official documentation",
        ),
    ]
    long_md = (
        "Use create-next-app to scaffold a new project. Run pnpm create next-app@latest my-app. "
        "The App Router uses a file-system based router where folders define routes. "
        "Add a layout.tsx file to share UI between multiple pages. "
        "Configure Tailwind by installing the package and adding the postcss plugin."
    )
    mock_client.scrape_markdown.return_value = ("Next.js Docs", long_md)

    passages = research_tutorial_via_firecrawl({
        "life_event": "Build with Next.js",
        "stack": "Next.js",
    })

    assert len(passages) == 1
    assert passages[0]["source_type"] == "official_docs"
    assert "create-next-app" in passages[0]["text"]


@patch("research.retrieval.settings")
@patch("research.retrieval._retrieve_from_firecrawl")
def test_retrieve_passages_prefers_firecrawl(mock_firecrawl, mock_settings) -> None:
    mock_settings.get_firecrawl_api_key.return_value = "fc-test"
    mock_firecrawl.return_value = [
        __import__("research.retrieval", fromlist=["RetrievedPassage"]).RetrievedPassage(
            passage_id="fc-001",
            text="Install dependencies with pnpm install before running the dev server.",
            source="Docs (https://example.com)",
            source_type="official_docs",
            jurisdiction_tags=["web"],
            relevance_score=1.0,
        )
    ]

    passages = retrieve_passages(
        query_keywords=["nextjs"],
        life_event="Build a Next.js app",
        brief={"life_event": "Build a Next.js app", "stack": "Next.js"},
    )
    assert len(passages) == 1
    mock_firecrawl.assert_called_once()


def test_firecrawl_client_requires_api_key() -> None:
    with patch("research.firecrawl_client.settings") as mock_settings:
        mock_settings.get_firecrawl_api_key.return_value = ""
        with pytest.raises(FirecrawlError, match="not configured"):
            research_tutorial_via_firecrawl({"life_event": "test"})
