"""
Error types for the model integration layer.

Three distinct failure modes, each carrying enough context for callers to
decide whether to retry, surface to the user, or abort the pipeline:

  ModelProviderError   — transport/API failure (rate limit, timeout, auth)
  ModelOutputError     — model responded but content is unusable
  OutputValidationError — model content parsed but fails structural contract
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# ModelProviderError
# ---------------------------------------------------------------------------

class ModelProviderError(Exception):
    """
    Raised when the model provider cannot be reached or returns a transport-level
    error: rate limit, authentication failure, timeout, or network error.

    These are retriable in principle — the pipeline service may choose to
    surface them as "failed" stage status with the original message.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        status_code: int | None = None,
        retries_exhausted: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retries_exhausted = retries_exhausted

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.status_code:
            parts.append(f"status={self.status_code}")
        if self.retries_exhausted:
            parts.append("retries_exhausted=True")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# ModelOutputError
# ---------------------------------------------------------------------------

class ModelOutputError(Exception):
    """
    Raised when the model returned a response but the content cannot be used:
    JSON parse failure, empty response, truncated output, or failed repair.

    Carries the raw text so callers can log it for debugging without
    exposing it to end users.
    """

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        contract_name: str | None = None,
        raw_text: str = "",
        parse_error: str = "",
        repair_attempted: bool = False,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.contract_name = contract_name
        self.raw_text = raw_text
        self.parse_error = parse_error
        self.repair_attempted = repair_attempted

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.stage:
            parts.append(f"stage={self.stage}")
        if self.contract_name:
            parts.append(f"contract={self.contract_name}")
        if self.parse_error:
            parts.append(f"parse_error={self.parse_error[:120]}")
        return " | ".join(parts)

    def truncated_raw(self, max_chars: int = 400) -> str:
        """Return the raw text, truncated to max_chars for logging."""
        if len(self.raw_text) <= max_chars:
            return self.raw_text
        return self.raw_text[:max_chars] + f"... [{len(self.raw_text)} chars total]"


# ---------------------------------------------------------------------------
# OutputValidationError
# ---------------------------------------------------------------------------

@dataclass
class FieldError:
    field: str
    reason: str
    actual_type: str | None = None
    expected_type: str | None = None


class OutputValidationError(Exception):
    """
    Raised when model output parses as valid JSON but fails the structural
    contract: missing required fields, wrong types, or empty values where
    content is required.

    This is NOT retriable by default — the model returned a structurally
    wrong answer for this contract.  The pipeline service records it as a
    failed stage so the user can re-run.
    """

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        field_errors: list[FieldError] | None = None,
        output_keys: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.field_errors = field_errors or []
        self.output_keys = output_keys or []

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.field_errors:
            errs = "; ".join(f"{e.field}: {e.reason}" for e in self.field_errors[:5])
            parts.append(f"field_errors=[{errs}]")
        return " | ".join(parts)

    @property
    def missing_fields(self) -> list[str]:
        return [e.field for e in self.field_errors if e.reason == "missing"]

    @property
    def type_errors(self) -> list[str]:
        return [e.field for e in self.field_errors if e.reason == "wrong_type"]
