"""BaseRule — abstract contract for all validation rules."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from validators.defect import Defect, Severity


class BaseRule(ABC):
    rule_id:   str
    severity:  Severity
    code:      str
    title:     str
    blocked_handoff: bool = True

    @abstractmethod
    def check(
        self,
        stage_output: dict[str, Any],
        context: dict[str, Any],
    ) -> list[Defect]:
        """
        Run this rule against stage_output.

        Args:
            stage_output: The parsed JSON output for this stage.
            context:      Dict that may contain other stage outputs under
                          their stage name keys, plus 'project' metadata.

        Returns:
            List of Defect objects — empty list means this rule passed.
        """

    def _defect(
        self,
        stage: str,
        field_path: str,
        evidence: str,
        message: str,
        required_fix: str,
        severity: Severity | None = None,
        blocked_handoff: bool | None = None,
    ) -> Defect:
        return Defect(
            stage=stage,
            rule_id=self.rule_id,
            severity=severity or self.severity,
            code=self.code,
            title=self.title,
            field_path=field_path,
            evidence=evidence[:400] if evidence else "(none)",
            message=message,
            required_fix=required_fix,
            blocked_handoff=blocked_handoff if blocked_handoff is not None else self.blocked_handoff,
        )
