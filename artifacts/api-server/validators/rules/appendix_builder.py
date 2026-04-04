"""
Stage 4 — Appendix Builder rule set.

Rules:
  APPENDIX_NO_SECTIONS       fatal  — appendix_sections is absent or empty
  APPENDIX_MISSING_CONTENT   error  — a section has no content or content is empty
  APPENDIX_MISSING_TITLE     error  — a section has no title or label
  APPENDIX_SHORT_CONTENT     warning — a section's content is under 50 words
"""
from __future__ import annotations

from typing import Any

from validators.defect import Defect, Severity
from validators.rules.base import BaseRule

STAGE = "appendix_builder"


class NoSectionsRule(BaseRule):
    rule_id  = "APPENDIX_NO_SECTIONS"
    severity = Severity.fatal
    code     = "APPENDIX_NO_SECTIONS"
    title    = "Appendix Builder Produced No Sections"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        sections = (
            stage_output.get("appendix_sections")
            or stage_output.get("sections")
            or []
        )
        if not sections:
            return [self._defect(
                stage=STAGE,
                field_path="appendix_sections",
                evidence="(absent or empty)",
                message="Appendix builder produced no sections. Output must contain at least one appendix section.",
                required_fix="Re-run appendix_builder with force=true.",
            )]
        return []


class MissingContentRule(BaseRule):
    rule_id  = "APPENDIX_MISSING_CONTENT"
    severity = Severity.error
    code     = "APPENDIX_MISSING_CONTENT"
    title    = "Appendix Section Missing Content"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        sections = (
            stage_output.get("appendix_sections")
            or stage_output.get("sections")
            or []
        )
        defects = []
        for i, sec in enumerate(sections):
            content = (
                sec.get("content")
                or sec.get("body")
                or sec.get("text")
                or ""
            )
            if not str(content).strip():
                label = sec.get("title") or sec.get("label") or f"section[{i}]"
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"appendix_sections[{i}].content",
                    evidence="(empty or absent)",
                    message=f"Appendix section '{label}' has no content.",
                    required_fix="Re-run appendix_builder with force=true.",
                ))
        return defects


class MissingTitleRule(BaseRule):
    rule_id  = "APPENDIX_MISSING_TITLE"
    severity = Severity.error
    code     = "APPENDIX_MISSING_TITLE"
    title    = "Appendix Section Missing Title"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        sections = (
            stage_output.get("appendix_sections")
            or stage_output.get("sections")
            or []
        )
        defects = []
        for i, sec in enumerate(sections):
            title = (sec.get("title") or sec.get("label") or "").strip()
            if not title:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"appendix_sections[{i}].title",
                    evidence="(absent or empty)",
                    message=f"Appendix section at index {i} has no title or label.",
                    required_fix="Re-run appendix_builder with force=true.",
                ))
        return defects


class ShortContentRule(BaseRule):
    rule_id  = "APPENDIX_SHORT_CONTENT"
    severity = Severity.warning
    code     = "APPENDIX_SHORT_CONTENT"
    title    = "Appendix Section Content Too Brief"
    blocked_handoff = False

    _MIN_WORDS = 50

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        sections = (
            stage_output.get("appendix_sections")
            or stage_output.get("sections")
            or []
        )
        defects = []
        for i, sec in enumerate(sections):
            content = sec.get("content") or sec.get("body") or sec.get("text") or ""
            word_count = len(str(content).split())
            if 0 < word_count < self._MIN_WORDS:
                label = sec.get("title") or sec.get("label") or f"section[{i}]"
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"appendix_sections[{i}].content",
                    evidence=f"{word_count} words (minimum {self._MIN_WORDS} recommended)",
                    message=f"Appendix section '{label}' is very short ({word_count} words).",
                    required_fix="Review appendix_builder output quality; re-run if content is insufficient.",
                ))
        return defects


APPENDIX_BUILDER_RULES: list[BaseRule] = [
    NoSectionsRule(),
    MissingContentRule(),
    MissingTitleRule(),
    ShortContentRule(),
]
