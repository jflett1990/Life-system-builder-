"""
Stage 3 — Chapter Expansion rule set.

Rules:
  CHAP_NO_CHAPTERS           fatal  — chapters list is absent or empty
  CHAP_MISSING_NARRATIVE     error  — a chapter has no narrative or narrative is under 200 words
  CHAP_MISSING_TITLE         error  — a chapter entry has no chapter_title or domain_name
  CHAP_MISSING_WORKSHEET_LINKAGE warning — a chapter has no worksheet linkage guidance
  CHAP_PARTIAL_FAILURE       error  — any chapter is marked failed or error
  CHAP_OPENER_INCOMPLETE     error  — chapter opener missing required orientation fields
  CHAP_ACTION_MODE_WEAK      warning — insufficient action/trigger structures
  CHAP_DENSE_PROSE           warning — oversized paragraphs or missing orientation heading
"""
from __future__ import annotations

from typing import Any
import re

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


class MissingWorksheetLinkageRule(BaseRule):
    rule_id  = "CHAP_MISSING_WORKSHEET_LINKAGE"
    severity = Severity.warning
    code     = "CHAP_MISSING_WORKSHEET_LINKAGE"
    title    = "Chapter Missing Worksheet Linkage Guidance"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        chapters = stage_output.get("chapters") or stage_output.get("expanded_chapters") or []
        defects = []
        for chap in chapters:
            num = chap.get("chapter_number", "?")
            worksheet_linkage = chap.get("worksheet_linkage") or []
            if not worksheet_linkage:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"chapters[{num}].worksheet_linkage",
                    evidence="(empty list)",
                    message=f"Chapter {num} does not explain when worksheets should be used.",
                    required_fix=f"Re-expand chapter {num} and require worksheet_linkage blocks tied to execution timing.",
                ))
        return defects


class IncompleteOpenerRule(BaseRule):
    rule_id  = "CHAP_OPENER_INCOMPLETE"
    severity = Severity.error
    code     = "CHAP_OPENER_INCOMPLETE"
    title    = "Chapter Opener Missing Orientation Fields"
    blocked_handoff = False

    _REQUIRED_KEYS = (
        "what_this_is_for",
        "when_it_matters",
        "failure_looks_like",
        "produces",
        "do_first",
    )

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        chapters = stage_output.get("chapters") or stage_output.get("expanded_chapters") or []
        defects = []
        for chap in chapters:
            num = chap.get("chapter_number", "?")
            opener = chap.get("chapter_opener") or {}
            missing = [k for k in self._REQUIRED_KEYS if not opener.get(k)]
            if missing:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"chapters[{num}].chapter_opener",
                    evidence=f"missing: {', '.join(missing)}",
                    message=f"Chapter {num} opener is incomplete; users will not be oriented quickly under stress.",
                    required_fix="Regenerate chapter structure with a complete chapter_opener object.",
                ))
        return defects


class ActionModeCoverageRule(BaseRule):
    rule_id  = "CHAP_ACTION_MODE_WEAK"
    severity = Severity.warning
    code     = "CHAP_ACTION_MODE_WEAK"
    title    = "Chapter Has Weak Action/Trigger Coverage"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        chapters = stage_output.get("chapters") or stage_output.get("expanded_chapters") or []
        defects = []
        for chap in chapters:
            num = chap.get("chapter_number", "?")
            mva = chap.get("minimum_viable_actions") or []
            decisions = chap.get("decision_guide") or []
            triggers = chap.get("trigger_blocks") or []
            risks = chap.get("risk_blocks") or []
            if len(mva) < 3 or len(decisions) < 3 or len(triggers) < 2 or len(risks) < 2:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"chapters[{num}]",
                    evidence=f"mva={len(mva)}, decisions={len(decisions)}, triggers={len(triggers)}, risks={len(risks)}",
                    message=f"Chapter {num} under-serves scan/action mode; critical guidance may remain buried in prose.",
                    required_fix="Regenerate structure with richer minimum_viable_actions, decision_guide, trigger_blocks, and risk_blocks.",
                ))
        return defects


class DenseProseRule(BaseRule):
    rule_id  = "CHAP_DENSE_PROSE"
    severity = Severity.warning
    code     = "CHAP_DENSE_PROSE"
    title    = "Chapter Prose Density Too High"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        chapters = stage_output.get("chapters") or stage_output.get("expanded_chapters") or []
        defects = []
        for chap in chapters:
            num = chap.get("chapter_number", "?")
            narrative = chap.get("narrative") or ""

            if narrative and "## Orientation Snapshot" not in narrative:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"chapters[{num}].narrative",
                    evidence="missing heading ## Orientation Snapshot",
                    message=f"Chapter {num} narrative is missing required orientation heading.",
                    required_fix="Regenerate chapter narrative with required layered heading structure.",
                ))

            paragraphs = [
                p.strip() for p in re.split(r"\n{2,}", narrative)
                if p.strip() and not p.strip().startswith("## ")
            ]
            overlong = [p for p in paragraphs if len(p.split()) > 140]
            if overlong:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"chapters[{num}].narrative",
                    evidence=f"{len(overlong)} paragraph(s) > 140 words",
                    message=f"Chapter {num} has dense prose paragraphs that reduce scannability.",
                    required_fix="Split long paragraphs and elevate logic into structured blocks.",
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
    MissingWorksheetLinkageRule(),
    PartialFailureRule(),
    IncompleteOpenerRule(),
    ActionModeCoverageRule(),
    DenseProseRule(),
]
