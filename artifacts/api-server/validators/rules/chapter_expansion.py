"""
Stage 3 — Chapter Expansion rule set.

Rules:
  CHAP_NO_CHAPTERS           fatal  — chapters list is absent or empty
  CHAP_MISSING_NARRATIVE     error  — a chapter has no narrative or narrative is under 200 words
  CHAP_MISSING_TITLE         error  — a chapter entry has no chapter_title or domain_name
  CHAP_MISSING_WORKSHEETS    warning — a chapter has zero worksheets
  CHAP_PARTIAL_FAILURE       error  — any chapter is marked failed or error
"""
from __future__ import annotations

from typing import Any

from validators.defect import Defect, Severity
from validators.rules.base import BaseRule

STAGE = "chapter_expansion"


class NoChaptersRule(BaseRule):
    rule_id  = "CHAP_NO_CHAPTERS"
    severity = Severity.fatal
    code     = "CHAP_NO_CHAPTERS"
    title    = "Chapter Expansion Produced No Chapters"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        chapters = stage_output.get("chapters") or stage_output.get("expanded_chapters") or []
        if not chapters:
            return [self._defect(
                stage=STAGE,
                field_path="chapters",
                evidence="(empty or absent)",
                message="Chapter expansion produced no chapters. The output must contain at least one expanded chapter.",
                required_fix="Re-run chapter_expansion with force=true.",
            )]
        return []


class MissingNarrativeRule(BaseRule):
    rule_id  = "CHAP_MISSING_NARRATIVE"
    severity = Severity.error
    code     = "CHAP_MISSING_NARRATIVE"
    title    = "Chapter Missing Narrative Content"
    blocked_handoff = False

    _MIN_WORDS = 200

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        chapters = stage_output.get("chapters") or stage_output.get("expanded_chapters") or []
        defects = []
        for chap in chapters:
            num = chap.get("chapter_number", "?")
            narrative = chap.get("narrative") or chap.get("chapter_narrative") or ""
            word_count = len(str(narrative).split()) if narrative else 0
            if word_count < self._MIN_WORDS:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"chapters[{num}].narrative",
                    evidence=f"{word_count} words (minimum {self._MIN_WORDS})",
                    message=f"Chapter {num} narrative is too short ({word_count} words). Minimum is {self._MIN_WORDS} words.",
                    required_fix=f"Re-expand chapter {num} with force=true.",
                ))
        return defects


class MissingTitleRule(BaseRule):
    rule_id  = "CHAP_MISSING_TITLE"
    severity = Severity.error
    code     = "CHAP_MISSING_TITLE"
    title    = "Chapter Entry Missing Title"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        chapters = stage_output.get("chapters") or stage_output.get("expanded_chapters") or []
        defects = []
        for chap in chapters:
            num = chap.get("chapter_number", "?")
            title = (
                chap.get("chapter_title")
                or chap.get("domain_name")
                or chap.get("title")
                or ""
            ).strip()
            if not title:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"chapters[{num}].chapter_title",
                    evidence="(absent or empty)",
                    message=f"Chapter {num} has no title or domain_name.",
                    required_fix=f"Re-expand chapter {num} with force=true.",
                ))
        return defects


class MissingWorksheetsRule(BaseRule):
    rule_id  = "CHAP_MISSING_WORKSHEETS"
    severity = Severity.warning
    code     = "CHAP_MISSING_WORKSHEETS"
    title    = "Chapter Has No Worksheets"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        chapters = stage_output.get("chapters") or stage_output.get("expanded_chapters") or []
        defects = []
        for chap in chapters:
            num = chap.get("chapter_number", "?")
            worksheets = chap.get("worksheets") or []
            if not worksheets:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"chapters[{num}].worksheets",
                    evidence="(empty list)",
                    message=f"Chapter {num} contains no worksheets.",
                    required_fix=f"Re-expand chapter {num} or verify LLM output includes worksheets array.",
                ))
        return defects


class PartialFailureRule(BaseRule):
    rule_id  = "CHAP_PARTIAL_FAILURE"
    severity = Severity.error
    code     = "CHAP_PARTIAL_FAILURE"
    title    = "One or More Chapters Failed to Expand"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        chapters = stage_output.get("chapters") or stage_output.get("expanded_chapters") or []
        defects = []
        for chap in chapters:
            num = chap.get("chapter_number", "?")
            status = str(chap.get("status", "")).lower()
            if status in ("failed", "error"):
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"chapters[{num}].status",
                    evidence=status,
                    message=f"Chapter {num} is marked '{status}' in chapter_expansion output.",
                    required_fix=f"Re-run chapter_expansion with force=true to retry failed chapters.",
                ))
        return defects


CHAPTER_EXPANSION_RULES: list[BaseRule] = [
    NoChaptersRule(),
    MissingNarrativeRule(),
    MissingTitleRule(),
    MissingWorksheetsRule(),
    PartialFailureRule(),
]
