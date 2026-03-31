"""
StageOutputParser — validates model-generated JSON against Pydantic stage schemas.

Responsibilities:
  - Look up the Pydantic schema for a stage by name
  - Attempt model_validate on the raw dict
  - Return a ParseResult with structured error information on failure
  - Convert validation errors into human-readable messages for logging and retry prompts

ParseResult captures both raw_data (unvalidated dict) and parsed_data (Pydantic-validated
dict via model_dump) so that:
  - The pipeline always has the raw model output for debugging
  - On success, the pipeline can use the schema-coerced data
  - On failure, the pipeline knows exactly which fields failed

Never raises — always returns a ParseResult. Callers decide whether to retry or fail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from core.logging import get_logger
from schemas.stage_outputs import get_schema

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# ParseResult
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    """
    Result of parsing and validating a stage output dict against its Pydantic schema.

    Attributes:
        stage:             Pipeline stage name.
        success:           True if Pydantic validation passed.
        parsed_data:       Schema-validated dict (model_dump) — None if validation failed.
        raw_data:          Unvalidated dict from JSON extraction — always set.
        raw_text:          Original model response string — always set.
        validation_errors: Human-readable error messages — empty if success.
        schema_name:       Name of the Pydantic class used (e.g. "SystemArchitectureOutput").
        attempt:           Which attempt number this result is from (1-indexed).
        has_schema:        False if no schema is registered for this stage.
    """
    stage: str
    success: bool
    parsed_data: dict[str, Any] | None
    raw_data: dict[str, Any]
    raw_text: str
    validation_errors: list[str] = field(default_factory=list)
    schema_name: str = "none"
    attempt: int = 1
    has_schema: bool = True

    def error_summary(self, max_errors: int = 5) -> str:
        if not self.validation_errors:
            return "no errors"
        shown = self.validation_errors[:max_errors]
        suffix = f" (+{len(self.validation_errors) - max_errors} more)" if len(self.validation_errors) > max_errors else ""
        return "; ".join(shown) + suffix

    def for_error_message(self) -> str:
        """Format for storage in stage_output.error_message."""
        lines = [f"Schema validation failed (attempt {self.attempt}):"]
        for err in self.validation_errors[:10]:
            lines.append(f"  • {err}")
        if len(self.validation_errors) > 10:
            lines.append(f"  (+{len(self.validation_errors) - 10} more errors)")
        lines.append("Raw output preserved in raw_model_output column.")
        return "\n".join(lines)

    def for_retry_prompt(self) -> str:
        """Format for the schema repair user message sent to the model."""
        import json as _json

        lines = [
            f"Your previous response for stage '{self.stage}' failed schema validation.",
            f"You must fix the following {len(self.validation_errors)} error(s):",
            "",
        ]
        for i, err in enumerate(self.validation_errors[:8], 1):
            lines.append(f"  {i}. {err}")
        if len(self.validation_errors) > 8:
            lines.append(f"  ... and {len(self.validation_errors) - 8} more errors.")

        # Show the extracted (parsed) dict when available — it's cleaner than the
        # potentially-malformed raw_text and helps the model understand what it produced.
        if self.raw_data:
            try:
                shown = _json.dumps(self.raw_data, indent=2)
                shown = shown[:1500] + ("..." if len(shown) > 1500 else "")
                label = "Your previous response (as parsed):"
            except Exception:
                shown = self.raw_text[:1500] + ("..." if len(self.raw_text) > 1500 else "")
                label = "Your previous (invalid) response was:"
        else:
            shown = self.raw_text[:1500] + ("..." if len(self.raw_text) > 1500 else "")
            label = "Your previous (invalid) response was:"

        lines += [
            "",
            label,
            "---",
            shown,
            "---",
            "",
            "Instructions:",
            "• Return the COMPLETE corrected JSON object — not just the fixed fields.",
            "• All required fields must be present at the TOP LEVEL (not nested).",
            "• All required fields must be non-empty.",
            "• Return ONLY valid JSON. No markdown. No prose. No code fences.",
            "• The first character must be '{' and the last must be '}'.",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class StageOutputParser:
    """
    Validates model output dicts against registered Pydantic stage schemas.

    Usage:
        parser = StageOutputParser()
        result = parser.parse(stage, data, raw_text, attempt=1)
        if not result.success:
            logger.warning(result.error_summary())
    """

    def parse(
        self,
        stage: str,
        data: dict[str, Any],
        raw_text: str,
        attempt: int = 1,
    ) -> ParseResult:
        """
        Validate `data` against the Pydantic schema for `stage`.

        Args:
            stage:    Pipeline stage name (underscores).
            data:     Raw dict from JSON extraction (unvalidated).
            raw_text: Original model response string.
            attempt:  Attempt number (for logging/error messages).

        Returns:
            ParseResult — always. Never raises.
        """
        schema_class = get_schema(stage)

        if schema_class is None:
            logger.debug("No schema registered for stage '%s' — skipping validation", stage)
            return ParseResult(
                stage=stage,
                success=True,  # No schema = no constraint = pass through
                parsed_data=data,
                raw_data=data,
                raw_text=raw_text,
                schema_name="none",
                attempt=attempt,
                has_schema=False,
            )

        schema_name = schema_class.__name__

        try:
            validated = schema_class.model_validate(data)
            parsed_data = validated.model_dump()

            logger.debug(
                "ParseResult | stage=%s | schema=%s | attempt=%d | PASS",
                stage, schema_name, attempt,
            )
            return ParseResult(
                stage=stage,
                success=True,
                parsed_data=parsed_data,
                raw_data=data,
                raw_text=raw_text,
                schema_name=schema_name,
                attempt=attempt,
                has_schema=True,
            )

        except ValidationError as exc:
            errors = _format_pydantic_errors(exc)
            logger.warning(
                "ParseResult | stage=%s | schema=%s | attempt=%d | FAIL | %d error(s): %s",
                stage, schema_name, attempt, len(errors),
                "; ".join(errors[:3]),
            )
            return ParseResult(
                stage=stage,
                success=False,
                parsed_data=None,
                raw_data=data,
                raw_text=raw_text,
                validation_errors=errors,
                schema_name=schema_name,
                attempt=attempt,
                has_schema=True,
            )

        except Exception as exc:
            logger.error(
                "ParseResult | stage=%s | unexpected error during schema validation: %s",
                stage, exc,
            )
            return ParseResult(
                stage=stage,
                success=False,
                parsed_data=None,
                raw_data=data,
                raw_text=raw_text,
                validation_errors=[f"Unexpected validation error: {exc}"],
                schema_name=schema_name,
                attempt=attempt,
                has_schema=True,
            )


# ---------------------------------------------------------------------------
# Error formatting helpers
# ---------------------------------------------------------------------------

def _format_pydantic_errors(exc: ValidationError) -> list[str]:
    """
    Convert a Pydantic ValidationError into a list of human-readable strings.

    Each string is of the form:
        field_path: error_message (input_type → expected_type)

    These strings are used in:
      1. ParseResult.error_summary() — for logs
      2. ParseResult.for_retry_prompt() — sent back to the model
      3. ParseResult.for_error_message() — stored in stage_output.error_message
    """
    messages: list[str] = []
    for error in exc.errors(include_url=False):
        loc = ".".join(str(p) for p in error.get("loc", []))
        msg = error.get("msg", "invalid value")
        err_type = error.get("type", "")
        input_val = error.get("input")

        # Shorten common Pydantic error types
        friendly = _friendly_type(err_type, msg)

        if input_val is not None and not isinstance(input_val, dict):
            input_str = repr(input_val)[:60]
            messages.append(f"{loc or 'root'}: {friendly} (got {input_str})")
        else:
            messages.append(f"{loc or 'root'}: {friendly}")

    return messages


def _friendly_type(err_type: str, msg: str) -> str:
    """Map Pydantic error type codes to readable descriptions."""
    _MAP = {
        "missing":           "field is required but missing",
        "string_type":       "must be a string",
        "int_type":          "must be an integer",
        "bool_type":         "must be a boolean",
        "list_type":         "must be a list/array",
        "dict_type":         "must be an object",
        "too_short":         "list must not be empty (min_length=1)",
        "string_too_short":  "string must not be empty (min_length=1)",
        "greater_than_equal":"must be >= 0",
        "value_error":       "value error",
    }
    for key, friendly in _MAP.items():
        if err_type.startswith(key):
            return friendly
    return msg
