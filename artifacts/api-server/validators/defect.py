"""
Defect model, severity enum, and verdict enum for the compiler-style validation engine.

Design contract:
  - every Defect must carry an evidence field — the actual value that triggered the rule
  - blocked_handoff=True means downstream processing cannot proceed regardless of verdict
  - Verdict is computed by the engine, never by individual rules
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Literal


class Severity(str, Enum):
    fatal   = "fatal"    # structural impossibility — pipeline cannot continue
    error   = "error"    # defect that must be fixed before handoff
    warning = "warning"  # defect that should be fixed but allows conditional handoff
    info    = "info"     # observation only — no action required


SEVERITY_ORDER = {Severity.fatal: 0, Severity.error: 1, Severity.warning: 2, Severity.info: 3}


class Verdict(str, Enum):
    passed           = "pass"
    failed           = "fail"
    conditional_pass = "conditional_pass"


@dataclass
class Defect:
    stage:          str
    rule_id:        str
    severity:       Severity
    code:           str
    title:          str
    field_path:     str
    evidence:       str          # the actual value that triggered this defect — never empty
    message:        str          # human-readable description
    required_fix:   str          # specific corrective action — not a suggestion
    blocked_handoff: bool        # true blocks downstream processing even on conditional_pass
    defect_id:      str = field(default_factory=lambda: f"DEF-{uuid.uuid4().hex[:6].upper()}")

    def to_dict(self) -> dict:
        return {
            "defect_id":      self.defect_id,
            "stage":          self.stage,
            "rule_id":        self.rule_id,
            "severity":       self.severity.value,
            "code":           self.code,
            "title":          self.title,
            "field_path":     self.field_path,
            "evidence":       self.evidence,
            "message":        self.message,
            "required_fix":   self.required_fix,
            "blocked_handoff": self.blocked_handoff,
        }


def compute_verdict(defects: list[Defect]) -> Verdict:
    if not defects:
        return Verdict.passed

    severities = {d.severity for d in defects}
    any_handoff_blocker = any(d.blocked_handoff for d in defects)

    if Severity.fatal in severities or (Severity.error in severities and any_handoff_blocker):
        return Verdict.failed

    if Severity.error in severities:
        return Verdict.failed

    if Severity.warning in severities:
        return Verdict.conditional_pass

    return Verdict.passed


def sort_defects(defects: list[Defect]) -> list[Defect]:
    return sorted(defects, key=lambda d: (SEVERITY_ORDER[d.severity], d.stage, d.field_path))
