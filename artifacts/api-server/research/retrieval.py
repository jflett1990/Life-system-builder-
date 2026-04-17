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
    source_type: str          # government | legal | medical | financial | general
    jurisdiction_tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0


# ── Built-in snippet library (jurisdiction-tagged, Phase C stub) ───────────────
# A minimal curated set of high-confidence factual snippets for common life events.
# Phase D will replace this with a vector search over a full knowledge base.

_SNIPPET_LIBRARY: list[dict[str, Any]] = [
    {
        "text": "Probate is the court-supervised process of authenticating a deceased person's will and distributing estate assets. Required when the decedent owned assets solely in their name above state-specific thresholds (commonly $50,000–$185,000 depending on jurisdiction).",
        "source": "Uniform Probate Code / State Law",
        "source_type": "legal",
        "jurisdiction_tags": ["US", "probate", "estate"],
        "keywords": ["probate", "estate", "will", "deceased", "assets"],
    },
    {
        "text": "A durable power of attorney for healthcare remains valid even if the principal becomes incapacitated. Must be signed before incapacity occurs. State laws vary on witness and notarization requirements.",
        "source": "State Health Care Power of Attorney Statutes",
        "source_type": "legal",
        "jurisdiction_tags": ["US", "healthcare", "elder_care", "legal_documents"],
        "keywords": ["power of attorney", "healthcare proxy", "incapacity", "advance directive"],
    },
    {
        "text": "Medicare Part A covers inpatient hospital stays, skilled nursing facility care, hospice, and some home health care. Part B covers outpatient services, preventive care, and durable medical equipment. Enrollment windows apply.",
        "source": "Centers for Medicare & Medicaid Services (CMS)",
        "source_type": "government",
        "jurisdiction_tags": ["US", "medicare", "healthcare", "elder_care"],
        "keywords": ["medicare", "part a", "part b", "hospitalization", "skilled nursing"],
    },
    {
        "text": "Medicaid spend-down rules require applicants to reduce countable assets below state thresholds before qualifying. Lookback periods of 60 months apply to asset transfers. Rules vary significantly by state.",
        "source": "Medicaid State Programs / CMS",
        "source_type": "government",
        "jurisdiction_tags": ["US", "medicaid", "elder_care", "long_term_care"],
        "keywords": ["medicaid", "spend-down", "assets", "lookback", "long term care"],
    },
    {
        "text": "HIPAA grants patients the right to access their medical records within 30 days of request. Covered entities must provide records in the patient's requested format when readily producible. Fees limited to cost of production.",
        "source": "Health Insurance Portability and Accountability Act (HIPAA) / HHS",
        "source_type": "government",
        "jurisdiction_tags": ["US", "healthcare", "medical_records", "HIPAA"],
        "keywords": ["hipaa", "medical records", "access", "patient rights"],
    },
    {
        "text": "IRS Form 706 (Estate Tax Return) must be filed for estates exceeding the federal exemption ($13.61 million in 2024). Filing deadline is 9 months after the decedent's death, with a 6-month extension available.",
        "source": "Internal Revenue Service (IRS) — Publication 950",
        "source_type": "government",
        "jurisdiction_tags": ["US", "federal", "estate_tax", "probate"],
        "keywords": ["estate tax", "form 706", "irs", "inheritance", "exemption"],
    },
    {
        "text": "Real estate held in joint tenancy with right of survivorship passes automatically to the surviving owner(s) and does not go through probate. A new deed may be required to clear title. State requirements for recording vary.",
        "source": "State Property Law / Title Insurance Standards",
        "source_type": "legal",
        "jurisdiction_tags": ["US", "real_estate", "probate", "estate"],
        "keywords": ["joint tenancy", "survivorship", "deed", "title", "probate"],
    },
    {
        "text": "A living trust (revocable trust) allows assets to pass to beneficiaries outside of probate. The grantor retains control during their lifetime. Requires funding — assets must be retitled into the trust's name.",
        "source": "State Trust Law / Estate Planning Standards",
        "source_type": "legal",
        "jurisdiction_tags": ["US", "trust", "estate", "probate"],
        "keywords": ["living trust", "revocable trust", "probate avoidance", "funding"],
    },
    {
        "text": "Social Security survivor benefits are available to spouses, children under 18, and dependent parents of a deceased worker. Application must be made at a Social Security office. Benefits begin the month after the worker's death.",
        "source": "Social Security Administration (SSA)",
        "source_type": "government",
        "jurisdiction_tags": ["US", "social_security", "survivor_benefits", "estate"],
        "keywords": ["social security", "survivor", "death benefit", "spouse", "dependent"],
    },
    {
        "text": "A divorce decree terminates marital property rights but may not automatically update beneficiary designations on retirement accounts, life insurance, or payable-on-death accounts. These must be updated separately.",
        "source": "ERISA / State Family Law",
        "source_type": "legal",
        "jurisdiction_tags": ["US", "divorce", "beneficiary", "retirement", "estate"],
        "keywords": ["divorce", "beneficiary", "retirement account", "ira", "401k", "life insurance"],
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
    life_event: str = "",
    max_results: int = 12,
) -> list[RetrievedPassage]:
    """Retrieve relevant passages for the given keywords and jurisdiction.

    Phase C: searches the built-in snippet library.
    Phase D: will also search an external vector knowledge base.
    """
    # Expand keywords from life_event string
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
