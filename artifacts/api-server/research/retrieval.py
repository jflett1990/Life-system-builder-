"""
Retrieval — Stage 1 knowledge retrieval for the research graph.

Strategy (PDR §04, Stage 1):
  Hybrid approach combining:
    1. Jurisdiction-tagged passage lookup against a curated knowledge base
    2. Model-assisted extraction from retrieved passages (fact_extractor handles this)

In Phase C, the knowledge base is the project's own stage outputs plus a built-in
jurisdiction-tagged snippet library. Full vector search over an external KB is
a Phase D addition. This implementation provides the interface and makes the
retrieval replaceable without changing callers.

Retrieval returns RetrievedPassage objects — unstructured text + metadata.
The fact extractor converts these into structured ResearchFacts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievedPassage:
    passage_id: str
    text: str
    source: str
    source_type: str          # framework_docs | platform_docs | tooling_docs | general
    jurisdiction_tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0


# ── Built-in snippet library (Phase C stub) ────────────────────────────────────
# A minimal curated set of high-confidence factual snippets for common coding
# tutorial topics. Phase D will replace this with a vector search over a full
# knowledge base.

_SNIPPET_LIBRARY: list[dict[str, Any]] = [
    {
        "text": "Node.js LTS releases are supported for roughly 30 months and are the recommended baseline for tutorials and production apps. Most modern frameworks (Next.js 14+, Vite 5+) require Node 18.17 or newer; check with `node --version` before installing dependencies.",
        "source": "Node.js Release Working Group",
        "source_type": "platform_docs",
        "jurisdiction_tags": ["node", "javascript", "web", "tooling"],
        "keywords": ["node", "nodejs", "version", "lts", "npm", "javascript", "next.js", "vite"],
    },
    {
        "text": "In the Next.js App Router, components are Server Components by default. Any component using state, effects, or browser-only APIs must start with the \"use client\" directive, or the build fails with errors like 'useState is not defined' or 'createContext only works in Client Components'.",
        "source": "Next.js Documentation — App Router",
        "source_type": "framework_docs",
        "jurisdiction_tags": ["nextjs", "react", "web", "frontend"],
        "keywords": ["next.js", "nextjs", "app router", "use client", "server component", "react", "landing page"],
    },
    {
        "text": "Tailwind CSS only generates classes it can statically find in files matched by the content configuration. If styles silently fail to apply, the most common cause is a missing or incorrect content glob, or class names built by string concatenation at runtime.",
        "source": "Tailwind CSS Documentation — Content Configuration",
        "source_type": "framework_docs",
        "jurisdiction_tags": ["tailwind", "css", "web", "frontend"],
        "keywords": ["tailwind", "css", "content", "purge", "styles", "frontend", "landing page"],
    },
    {
        "text": "Environment variables prefixed with NEXT_PUBLIC_ (Next.js) or VITE_ (Vite) are inlined into the client bundle at build time and are publicly visible. Secrets such as service-role keys or API tokens must never use these prefixes and must only be read server-side.",
        "source": "Next.js / Vite Documentation — Environment Variables",
        "source_type": "framework_docs",
        "jurisdiction_tags": ["env", "security", "web", "deploy"],
        "keywords": ["environment variable", "env", "secret", "api key", "deploy", "security", "supabase"],
    },
    {
        "text": "Discord bots must enable privileged gateway intents (such as MESSAGE CONTENT) both in code and in the Discord Developer Portal. A bot with mismatched intents connects successfully but silently receives no message events — the most common cause of 'my bot does not respond'.",
        "source": "Discord Developer Documentation — Gateway Intents",
        "source_type": "platform_docs",
        "jurisdiction_tags": ["discord", "bot", "python", "api"],
        "keywords": ["discord", "bot", "intents", "message content", "discord.py", "slash command"],
    },
    {
        "text": "FastAPI apps are served by an ASGI server such as uvicorn. In containers, bind to 0.0.0.0 and read the port from the environment — binding to 127.0.0.1 inside Docker makes the service unreachable from outside the container, which presents as connection refused on the mapped port.",
        "source": "FastAPI / Uvicorn Documentation — Deployment",
        "source_type": "framework_docs",
        "jurisdiction_tags": ["fastapi", "python", "api", "deploy", "docker"],
        "keywords": ["fastapi", "uvicorn", "deploy", "docker", "port", "0.0.0.0", "api", "python"],
    },
    {
        "text": "Docker images should be built with a .dockerignore that excludes node_modules, virtual environments, and build artifacts. Copying dependency manifests first and installing before copying source code preserves layer caching and cuts rebuild times from minutes to seconds.",
        "source": "Docker Documentation — Best Practices for Writing Dockerfiles",
        "source_type": "tooling_docs",
        "jurisdiction_tags": ["docker", "deploy", "devops"],
        "keywords": ["docker", "dockerfile", "dockerignore", "layer", "cache", "build", "deploy"],
    },
    {
        "text": "Supabase row-level security (RLS) is enabled per table; with RLS on and no policies, all reads and writes with the anon key fail silently with empty results or 401s. Tutorials must create explicit policies for anon/authenticated roles before client-side queries will work.",
        "source": "Supabase Documentation — Row Level Security",
        "source_type": "platform_docs",
        "jurisdiction_tags": ["supabase", "database", "auth", "web"],
        "keywords": ["supabase", "rls", "row level security", "policy", "anon key", "database", "crud"],
    },
    {
        "text": "Git branches are cheap pointers; committing after every verified checkpoint gives a known-good rollback target. `git checkout -- .` discards uncommitted changes, and `git revert <sha>` undoes a specific commit without rewriting history — safer than reset on shared branches.",
        "source": "Pro Git Book — Git Basics",
        "source_type": "tooling_docs",
        "jurisdiction_tags": ["git", "tooling", "workflow"],
        "keywords": ["git", "commit", "branch", "revert", "rollback", "checkpoint", "version control"],
    },
    {
        "text": "Server-Sent Events (SSE) and chunked responses are the standard transports for streaming LLM output to browsers. Reverse proxies and serverless platforms often buffer responses by default; disabling buffering (e.g. X-Accel-Buffering: no) is required or streamed tokens arrive all at once.",
        "source": "MDN Web Docs — Server-Sent Events",
        "source_type": "platform_docs",
        "jurisdiction_tags": ["streaming", "ai", "web", "api"],
        "keywords": ["streaming", "sse", "server-sent events", "ai", "chat", "llm", "buffer", "proxy"],
    },
    {
        "text": "Chrome extensions using Manifest V3 replace background pages with service workers, which are terminated when idle. State must be persisted in chrome.storage rather than module-level variables, and long-lived connections must handle reconnection.",
        "source": "Chrome for Developers — Manifest V3",
        "source_type": "platform_docs",
        "jurisdiction_tags": ["chrome", "extension", "javascript", "web"],
        "keywords": ["chrome extension", "manifest v3", "service worker", "chrome.storage", "tabs", "browser"],
    },
    {
        "text": "Python virtual environments isolate per-project dependencies. Creating one with `python -m venv .venv` and activating it before `pip install` prevents version conflicts between projects — the most common cause of 'works on my machine' import errors in Python tutorials.",
        "source": "Python Documentation — venv",
        "source_type": "platform_docs",
        "jurisdiction_tags": ["python", "tooling", "environment"],
        "keywords": ["python", "venv", "virtual environment", "pip", "install", "dependencies"],
    },
]


def _score_passage(passage: dict[str, Any], keywords: list[str], jurisdiction: str | None) -> float:
    """Score a passage's relevance to the search keywords and jurisdiction."""
    score = 0.0
    text_lower = (passage["text"] + " " + " ".join(passage.get("keywords", []))).lower()

    for kw in keywords:
        kw_lower = kw.lower().strip()
        if kw_lower in text_lower:
            score += 1.0 / (1 + text_lower.index(kw_lower) / len(text_lower))

    if jurisdiction:
        jur_lower = jurisdiction.lower()
        tags = [t.lower() for t in passage.get("jurisdiction_tags", [])]
        if any(jur_lower in tag for tag in tags):
            score += 0.5

    return score


def retrieve_passages(
    query_keywords: list[str],
    jurisdiction: str | None = None,
    topic: str = "",
    max_results: int = 12,
) -> list[RetrievedPassage]:
    """Retrieve relevant passages for the given keywords and environment.

    Phase C: searches the built-in snippet library.
    Phase D: will also search an external vector knowledge base.
    """
    # Expand keywords from the tutorial topic string
    all_keywords = list(query_keywords)
    if topic:
        words = re.findall(r"\b\w{4,}\b", topic.lower())
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
