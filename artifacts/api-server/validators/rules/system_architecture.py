"""
Stage 1 — System Architecture rule set.

Rules:
  ARCH_REQUIRED_FIELD       fatal   — required top-level field absent or empty
  ARCH_SYSTEM_NAME_GENERIC  error   — system_name is a template placeholder or bare generic
  ARCH_NO_CONTROL_DOMAINS   fatal   — control_domains missing or zero entries
  ARCH_DOMAIN_MISSING_ID    error   — a domain object is missing its 'id' field
  ARCH_DOMAIN_EMPTY_SCOPE   error   — domain scope_in or primary_outputs are absent/empty
  ARCH_ROLES_INSUFFICIENT   error   — fewer than 2 key_roles defined
  ARCH_SUCCESS_CRITERIA_VAGUE error — any success_criteria item is < 8 words or reads as generic advice
  ARCH_PREMISE_ADVICE       error   — operating_premise uses advisory language instead of
                                      describing an operational challenge
"""
from __future__ import annotations

import re
from typing import Any

from validators.defect import Defect, Severity
from validators.rules.base import BaseRule

STAGE = "system_architecture"

REQUIRED_FIELDS = [
    "system_name", "life_event", "operating_premise", "system_objective",
    "time_horizon", "control_domains", "key_roles", "success_criteria",
    "failure_modes", "operating_constraints",
]

GENERIC_SYSTEM_NAME_PATTERNS = re.compile(
    r"^(life system|my system|operational system|management system|"
    r"system \d*|new system|[a-z]+ system)$",
    re.IGNORECASE,
)

ADVICE_VERBS = re.compile(
    r"\b(make sure|ensure|consider|try to|remember to|don.t forget|be aware|"
    r"you should|it.s important|it is important|you must|keep in mind)\b",
    re.IGNORECASE,
)

VAGUE_CRITERIA = re.compile(
    r"^(achieve success|stay organized|be efficient|manage well|"
    r"get through|handle everything|complete the process|do the right thing|"
    r"take care of|move forward)[\.,!]?$",
    re.IGNORECASE,
)


class RequiredFieldRule(BaseRule):
    rule_id  = "ARCH_REQUIRED_FIELD"
    severity = Severity.fatal
    code     = "ARCH_REQUIRED_FIELD"
    title    = "Required Architecture Field Missing or Empty"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for f in REQUIRED_FIELDS:
            val = stage_output.get(f)
            if val is None:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f,
                    evidence="(field absent)",
                    message=f"Required field '{f}' is completely absent from stage output.",
                    required_fix=f"The LLM must return a non-empty value for '{f}'. Re-run stage with force=true.",
                ))
            elif isinstance(val, (str, list, dict)) and not val:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f,
                    evidence="(empty value)",
                    message=f"Required field '{f}' is present but empty.",
                    required_fix=f"Re-run stage 1 with additional context so the model populates '{f}'.",
                ))
        return defects


class GenericSystemNameRule(BaseRule):
    rule_id  = "ARCH_SYSTEM_NAME_GENERIC"
    severity = Severity.error
    code     = "ARCH_SYSTEM_NAME_GENERIC"
    title    = "System Name Is Generic or Template-Level"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        name = stage_output.get("system_name", "")
        if not isinstance(name, str) or not name:
            return []
        placeholders = ("system", "life system", "my system", "operational system",
                        "[system name]", "system name", "name", "untitled")
        if name.strip().lower() in placeholders or GENERIC_SYSTEM_NAME_PATTERNS.match(name.strip()):
            return [self._defect(
                stage=STAGE,
                field_path="system_name",
                evidence=name,
                message=(
                    f"system_name '{name}' is a generic placeholder. "
                    "It must be a specific, named system that reflects the life event — "
                    "e.g. 'Estate Command System' or 'Caregiver Transition Protocol'."
                ),
                required_fix=(
                    "Re-run stage 1. The system_name must be derived from the specific "
                    "life event and contain at least one domain-specific noun."
                ),
            )]
        return []


class NoControlDomainsRule(BaseRule):
    rule_id  = "ARCH_NO_CONTROL_DOMAINS"
    severity = Severity.fatal
    code     = "ARCH_NO_CONTROL_DOMAINS"
    title    = "Control Domains Array Is Empty or Absent"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        domains = stage_output.get("control_domains")
        if not domains or not isinstance(domains, list) or len(domains) == 0:
            return [self._defect(
                stage=STAGE,
                field_path="control_domains",
                evidence=str(domains),
                message=(
                    "control_domains is empty or absent. At least 2 control domains are required "
                    "to map the operational system — without them the worksheet stage cannot generate "
                    "domain-linked worksheets."
                ),
                required_fix="Re-run stage 1. The model must produce at least 2 control_domains objects.",
            )]
        return []


class DomainMissingIdRule(BaseRule):
    rule_id  = "ARCH_DOMAIN_MISSING_ID"
    severity = Severity.error
    code     = "ARCH_DOMAIN_MISSING_ID"
    title    = "Control Domain Missing 'id' Field"
    blocked_handoff = True

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, domain in enumerate(stage_output.get("control_domains", [])):
            if not isinstance(domain, dict):
                continue
            if not domain.get("id"):
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"control_domains[{i}].id",
                    evidence=str(domain.get("name", f"(domain index {i})")),
                    message=(
                        f"Domain at index {i} ('{domain.get('name', 'unnamed')}') is missing the 'id' field. "
                        "Domain IDs are required for cross-stage reference by the worksheet and layout stages."
                    ),
                    required_fix=(
                        f"Add an 'id' field to this domain (e.g. 'domain-0{i+1}'). "
                        "Re-run stage 1 with force=true."
                    ),
                ))
        return defects


class DomainEmptyScopeRule(BaseRule):
    rule_id  = "ARCH_DOMAIN_EMPTY_SCOPE"
    severity = Severity.error
    code     = "ARCH_DOMAIN_EMPTY_SCOPE"
    title    = "Control Domain Has Empty Scope or No Primary Outputs"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        for i, domain in enumerate(stage_output.get("control_domains", [])):
            if not isinstance(domain, dict):
                continue
            domain_id = domain.get("id", f"index-{i}")
            if not domain.get("scope_in"):
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"control_domains[{i}].scope_in",
                    evidence=str(domain_id),
                    message=f"Domain '{domain_id}' has no scope_in entries. Without scope definition the domain is decorative.",
                    required_fix="Provide at least 2 scope_in items specifying what this domain governs.",
                ))
            if not domain.get("primary_outputs"):
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"control_domains[{i}].primary_outputs",
                    evidence=str(domain_id),
                    message=f"Domain '{domain_id}' has no primary_outputs. Downstream render cannot populate output tables.",
                    required_fix="Provide at least 1 primary_outputs item — a tangible deliverable this domain produces.",
                ))
        return defects


class InsufficientRolesRule(BaseRule):
    rule_id  = "ARCH_ROLES_INSUFFICIENT"
    severity = Severity.error
    code     = "ARCH_ROLES_INSUFFICIENT"
    title    = "Fewer Than 2 Key Roles Defined"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        roles = stage_output.get("key_roles", [])
        if not isinstance(roles, list) or len(roles) < 2:
            return [self._defect(
                stage=STAGE,
                field_path="key_roles",
                evidence=f"{len(roles) if isinstance(roles, list) else 0} role(s) defined",
                message=(
                    "At least 2 key roles are required to define an operational system. "
                    "A single role produces an unexecutable system with no accountability structure."
                ),
                required_fix="Re-run stage 1. Define at minimum a decision-maker and an executor role.",
            )]
        return []


class SuccessCriteriaVagueRule(BaseRule):
    rule_id  = "ARCH_SUCCESS_CRITERIA_VAGUE"
    severity = Severity.error
    code     = "ARCH_SUCCESS_CRITERIA_VAGUE"
    title    = "Success Criteria Are Vague or Advice-Disguised"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        defects = []
        criteria = stage_output.get("success_criteria", [])
        if not isinstance(criteria, list):
            return []
        for i, item in enumerate(criteria):
            if not isinstance(item, str):
                continue
            words = item.strip().split()
            if len(words) < 6:
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"success_criteria[{i}]",
                    evidence=item,
                    message=(
                        f"Success criterion '{item}' is only {len(words)} word(s). "
                        "A verifiable criterion must be specific enough to evaluate — "
                        "vague criteria cannot serve as audit gates."
                    ),
                    required_fix=(
                        "Rewrite this criterion as a specific, verifiable outcome with a "
                        "subject, condition, and measurement. Minimum 6 words."
                    ),
                    severity=Severity.warning,
                    blocked_handoff=False,
                ))
            elif VAGUE_CRITERIA.match(item.strip()):
                defects.append(self._defect(
                    stage=STAGE,
                    field_path=f"success_criteria[{i}]",
                    evidence=item,
                    message=f"Success criterion '{item}' is a generic phrase, not a verifiable outcome.",
                    required_fix="Replace with a measurable outcome specific to this life event.",
                    severity=Severity.error,
                    blocked_handoff=False,
                ))
        return defects


class PremiseAdviceRule(BaseRule):
    rule_id  = "ARCH_PREMISE_ADVICE"
    severity = Severity.error
    code     = "ARCH_PREMISE_ADVICE"
    title    = "Operating Premise Uses Advisory Language Instead of Operational Statement"
    blocked_handoff = False

    def check(self, stage_output: dict[str, Any], context: dict[str, Any]) -> list[Defect]:
        premise = stage_output.get("operating_premise", "")
        if not isinstance(premise, str) or not premise:
            return []
        if ADVICE_VERBS.search(premise):
            match = ADVICE_VERBS.search(premise)
            return [self._defect(
                stage=STAGE,
                field_path="operating_premise",
                evidence=premise,
                message=(
                    f"operating_premise contains advisory language ('{match.group(0)}'). "
                    "The premise must describe the core operational challenge as a factual "
                    "statement, not advice to the user."
                ),
                required_fix=(
                    "Rewrite operating_premise as a declarative operational statement: "
                    "'The executor must coordinate [X] across [Y] within [constraint].'"
                ),
            )]
        return []


SYSTEM_ARCHITECTURE_RULES: list[BaseRule] = [
    RequiredFieldRule(),
    GenericSystemNameRule(),
    NoControlDomainsRule(),
    DomainMissingIdRule(),
    DomainEmptyScopeRule(),
    InsufficientRolesRule(),
    SuccessCriteriaVagueRule(),
    PremiseAdviceRule(),
]
