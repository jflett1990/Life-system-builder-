"""
Reference Appendix (appendix_builder) rule set.

The appendix output shape is:
  glossary_terms:        [{term, definition}]
  professional_triggers: [{situation, professional_type, urgency}]  — "when to get help"
  key_resources:         [{organization, service, phone, website, hours}]

Rules:
  APPENDIX_NO_SECTIONS       fatal  — no glossary terms AND no help triggers
  APPENDIX_MISSING_CONTENT   error  — glossary terms without definitions / triggers without a help source
  APPENDIX_MISSING_TITLE     error  — glossary entries without a term / triggers without a situation
  APPENDIX_SHORT_CONTENT     warning — fewer entries than the contract minimums
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
    title    = "Appendix Builder Produced No Content"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        glossary = stage_output.get("glossary_terms") or []
        triggers = stage_output.get("professional_triggers") or []
        if not glossary and not triggers:
            return [self._defect(
                stage=STAGE,
                field_path="glossary_terms",
                evidence="(glossary_terms and professional_triggers both absent or empty)",
                message="Appendix builder produced no content. Output must contain glossary terms and 'when to get help' triggers.",
                required_fix="Re-run appendix_builder with force=true.",
            )]
        return []


class MissingContentRule(BaseRule):
    rule_id  = "APPENDIX_MISSING_CONTENT"
    severity = Severity.error
    code     = "APPENDIX_MISSING_CONTENT"
    title    = "Appendix Entry Missing Content"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, entry in enumerate(stage_output.get("glossary_terms") or []):
            if not str(entry.get("definition", "")).strip():
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"glossary_terms[{i}].definition",
                    evidence=str(entry.get("term", f"entry[{i}]")),
                    message=f"Glossary term '{entry.get('term', i)}' has no definition.",
                    required_fix="Re-run appendix_builder with force=true.",
                ))
        for i, trig in enumerate(stage_output.get("professional_triggers") or []):
            if not str(trig.get("professional_type", "")).strip():
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"professional_triggers[{i}].professional_type",
                    evidence=str(trig.get("situation", f"trigger[{i}]"))[:80],
                    message=f"Help trigger at index {i} does not name where to get help.",
                    required_fix="Re-run appendix_builder with force=true.",
                ))
        return defects


class MissingTitleRule(BaseRule):
    rule_id  = "APPENDIX_MISSING_TITLE"
    severity = Severity.error
    code     = "APPENDIX_MISSING_TITLE"
    title    = "Appendix Entry Missing Term or Situation"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, entry in enumerate(stage_output.get("glossary_terms") or []):
            if not str(entry.get("term", "")).strip():
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"glossary_terms[{i}].term",
                    evidence="(absent or empty)",
                    message=f"Glossary entry at index {i} has no term.",
                    required_fix="Re-run appendix_builder with force=true.",
                ))
        for i, trig in enumerate(stage_output.get("professional_triggers") or []):
            if not str(trig.get("situation", "")).strip():
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"professional_triggers[{i}].situation",
                    evidence="(absent or empty)",
                    message=f"Help trigger at index {i} has no situation description.",
                    required_fix="Re-run appendix_builder with force=true.",
                ))
        return defects


class ShortContentRule(BaseRule):
    rule_id  = "APPENDIX_SHORT_CONTENT"
    severity = Severity.warning
    code     = "APPENDIX_SHORT_CONTENT"
    title    = "Appendix Thinner Than Contract Minimums"
    blocked_handoff = False

    _MIN_GLOSSARY = 10
    _MIN_TRIGGERS = 5

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        glossary = stage_output.get("glossary_terms") or []
        triggers = stage_output.get("professional_triggers") or []
        if 0 < len(glossary) < self._MIN_GLOSSARY:
            defects.append(self._defect(
                stage=STAGE,
                field_path="glossary_terms",
                evidence=f"{len(glossary)} terms (minimum {self._MIN_GLOSSARY} recommended)",
                message=f"Glossary has only {len(glossary)} terms; the contract targets 15–25.",
                required_fix="Review appendix_builder output quality; re-run if content is insufficient.",
            ))
        if 0 < len(triggers) < self._MIN_TRIGGERS:
            defects.append(self._defect(
                stage=STAGE,
                field_path="professional_triggers",
                evidence=f"{len(triggers)} triggers (minimum {self._MIN_TRIGGERS} recommended)",
                message=f"'When to get help' has only {len(triggers)} triggers; the contract targets 8–12.",
                required_fix="Review appendix_builder output quality; re-run if content is insufficient.",
            ))
        return defects


APPENDIX_BUILDER_RULES: list[BaseRule] = [
    NoSectionsRule(),
    MissingContentRule(),
    MissingTitleRule(),
    ShortContentRule(),
]
