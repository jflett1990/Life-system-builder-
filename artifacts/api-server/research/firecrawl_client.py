"""
Firecrawl client — web research for tutorial grounding.

Uses Firecrawl search + scrape to fetch up-to-date documentation, tutorials,
and implementation guides relevant to a tutorial request.

Requires FIRECRAWL_API_KEY in the environment.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

FIRECRAWL_API_BASE = "https://api.firecrawl.dev/v1"
DEFAULT_SEARCH_LIMIT = 5
DEFAULT_SCRAPE_TIMEOUT_S = 45
MAX_MARKDOWN_CHARS = 12_000


@dataclass
class FirecrawlSearchResult:
    url: str
    title: str
    description: str


class FirecrawlError(Exception):
    """Raised when a Firecrawl API call fails."""


class FirecrawlClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = (api_key or settings.get_firecrawl_api_key()).strip()
        if not self._api_key:
            raise FirecrawlError("FIRECRAWL_API_KEY is not configured")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout_s: int = DEFAULT_SCRAPE_TIMEOUT_S,
    ) -> dict[str, Any]:
        url = f"{FIRECRAWL_API_BASE}{path}"
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body if method != "GET" else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise FirecrawlError(f"Firecrawl HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise FirecrawlError(f"Firecrawl network error: {exc}") from exc

    def search(self, query: str, *, limit: int = DEFAULT_SEARCH_LIMIT) -> list[FirecrawlSearchResult]:
        data = self._request(
            "POST",
            "/search",
            {"query": query, "limit": limit},
            timeout_s=30,
        )
        if not data.get("success"):
            raise FirecrawlError(data.get("error", "Firecrawl search failed"))

        results: list[FirecrawlSearchResult] = []
        for item in data.get("data", []) or []:
            url = item.get("url", "")
            if not url:
                continue
            results.append(
                FirecrawlSearchResult(
                    url=url,
                    title=item.get("title", url),
                    description=item.get("description", ""),
                )
            )
        return results

    def scrape_markdown(self, url: str) -> tuple[str, str]:
        """Scrape a URL and return (title, markdown)."""
        data = self._request(
            "POST",
            "/scrape",
            {
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
            },
        )
        if not data.get("success"):
            raise FirecrawlError(data.get("error", f"Firecrawl scrape failed for {url}"))

        page = data.get("data", {}) or {}
        metadata = page.get("metadata", {}) or {}
        title = metadata.get("title") or metadata.get("ogTitle") or url
        markdown = (page.get("markdown") or "").strip()
        if len(markdown) > MAX_MARKDOWN_CHARS:
            markdown = markdown[:MAX_MARKDOWN_CHARS] + "\n\n[... truncated ...]"
        return title, markdown


def build_tutorial_search_queries(brief: dict[str, Any]) -> list[str]:
    """Build search queries from a tutorial project brief."""
    queries: list[str] = []
    tutorial = (brief.get("life_event") or brief.get("life_event_type") or "").strip()
    stack = (brief.get("stack") or "").strip()
    tutorial_type = (brief.get("tutorial_type") or "").strip()
    platform = (brief.get("platform") or "").strip()

    if tutorial:
        base = tutorial
        if stack:
            base = f"{tutorial} {stack}"
        queries.append(f"{base} tutorial official documentation")
        if tutorial_type in ("deployment guide", "debugging walkthrough"):
            queries.append(f"{tutorial} {tutorial_type}")
        elif platform:
            queries.append(f"{tutorial} deploy {platform}")

    for system in (brief.get("systems") or [])[:3]:
        name = system if isinstance(system, str) else system.get("name", "")
        if name:
            queries.append(f"{name} setup guide documentation")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique[:4]


def research_tutorial_via_firecrawl(
    brief: dict[str, Any],
    *,
    search_limit: int = 4,
    scrape_per_query: int = 2,
) -> list[dict[str, Any]]:
    """Search and scrape the web for tutorial-relevant content.

    Returns passage dicts compatible with retrieval.RetrievedPassage construction.
    """
    client = FirecrawlClient()
    queries = build_tutorial_search_queries(brief)
    if not queries:
        return []

    passages: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    passage_idx = 0

    for query in queries:
        logger.info("firecrawl | search query=%r", query[:120])
        try:
            hits = client.search(query, limit=search_limit)
        except FirecrawlError as exc:
            logger.warning("firecrawl | search failed for %r: %s", query, exc)
            continue

        scraped = 0
        for hit in hits:
            if hit.url in seen_urls:
                continue
            seen_urls.add(hit.url)
            try:
                title, markdown = client.scrape_markdown(hit.url)
                if len(markdown) < 200:
                    continue
                passage_idx += 1
                passages.append({
                    "passage_id": f"fc-{passage_idx:03d}",
                    "text": markdown,
                    "source": f"{title} ({hit.url})",
                    "source_type": _classify_source(hit.url),
                    "jurisdiction_tags": ["web", "tutorial"],
                    "relevance_score": 1.0 - (passage_idx * 0.05),
                })
                scraped += 1
                if scraped >= scrape_per_query:
                    break
                time.sleep(0.3)
            except FirecrawlError as exc:
                logger.warning("firecrawl | scrape failed for %s: %s", hit.url, exc)
                continue

    logger.info("firecrawl | collected %d passages from %d queries", len(passages), len(queries))
    return passages


def _classify_source(url: str) -> str:
    lower = url.lower()
    if any(d in lower for d in (
        "docs.", "documentation", "developer.", "readthedocs",
        "nextjs.org/docs", "python.org", "fastapi.tiangolo.com",
        "supabase.com/docs", "tailwindcss.com/docs",
    )):
        return "official_docs"
    if "github.com" in lower:
        return "professional"
    if any(d in lower for d in ("stackoverflow.com", "dev.to", "medium.com")):
        return "secondary"
    return "web"
