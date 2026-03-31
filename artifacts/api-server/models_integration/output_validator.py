"""
OutputValidator — structural validation of model-generated JSON.

Checks the model's output against the contract's:
  - required_output_fields  (presence + non-empty)
  - output_schema           (type hints for known JSON Schema types)

This is a purely structural check — no LLM calls, no semantic reasoning.
Semantic consistency is handled separately by the ValidationEngine.

Design:
  - Returns OutputValidation (never raises) so callers can decide how to handle errors
  - Type checking is best-effort: only validates simple JSON Schema primitives
    (string, integer, number, boolean, array, object) — ignores $ref / allOf / etc.
  - Unknown schema shapes are silently skipped (lenient by default)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class OutputValidation:
    """Result of a structural validation check against a contract."""
    stage: str | None
    valid: bool
    missing_fields: list[str] = field(default_factory=list)
    empty_fields: list[str] = field(default_factory=list)
    type_errors: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        """Flat list of all errors for logging."""
        errs: list[str] = []
        for f in self.missing_fields:
            errs.append(f"missing required field: '{f}'")
        for f in self.empty_fields:
            errs.append(f"empty required field: '{f}'")
        for e in self.type_errors:
            errs.append(e)
        return errs

    @property
    def error_summary(self) -> str:
        errs = self.errors
        if not errs:
            return "valid"
        return f"{len(errs)} validation error(s): " + "; ".join(errs[:5])

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "missing_fields": self.missing_fields,
            "empty_fields": self.empty_fields,
            "type_errors": self.type_errors,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

# JSON Schema primitive → Python types
_JSON_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string":  str,
    "integer": int,
    "number":  (int, float),
    "boolean": bool,
    "array":   list,
    "object":  dict,
}


class OutputValidator:
    """
    Validates model output against contract requirements.

    Usage:
        validator = OutputValidator()
        result = validator.validate(stage, output, required_fields, schema)
        if not result.valid:
            logger.warning(result.error_summary)
    """

    def validate(
        self,
        stage: str | None,
        output: dict[str, Any],
        required_fields: list[str],
        schema: dict[str, Any] | None = None,
    ) -> OutputValidation:
        """
        Run all structural checks and return an OutputValidation.

        Never raises — callers can inspect `.valid` and `.errors`.
        """
        missing: list[str] = []
        empty: list[str] = []
        type_errs: list[str] = []

        # 1 — Required field presence and non-empty check
        for field_name in required_fields:
            value = _deep_get(output, field_name)
            if value is _MISSING:
                missing.append(field_name)
            elif _is_empty(value):
                empty.append(field_name)

        # 2 — Schema type hints (best-effort, top-level properties only)
        if schema and isinstance(schema.get("properties"), dict):
            type_errs = self._check_types(output, schema["properties"])

        valid = not (missing or empty or type_errs)
        return OutputValidation(
            stage=stage,
            valid=valid,
            missing_fields=missing,
            empty_fields=empty,
            type_errors=type_errs,
        )

    def _check_types(
        self,
        output: dict[str, Any],
        properties: dict[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        for prop_name, prop_def in properties.items():
            if prop_name not in output:
                continue  # absence handled by required_fields check
            expected_json_type = prop_def.get("type")
            if not expected_json_type:
                continue
            py_type = _JSON_TYPE_MAP.get(expected_json_type)
            if py_type is None:
                continue  # unknown type — skip
            value = output[prop_name]
            if value is None:
                continue  # None is allowed; required check handles empties
            # Coerce: JSON integers are also valid numbers
            if expected_json_type == "number" and isinstance(value, bool):
                errors.append(
                    f"field '{prop_name}': expected number, got boolean"
                )
            elif not isinstance(value, py_type):
                actual = type(value).__name__
                errors.append(
                    f"field '{prop_name}': expected {expected_json_type}, got {actual}"
                )
        return errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MISSING = object()


def _deep_get(obj: dict[str, Any], dotted_key: str) -> Any:
    """
    Resolve a key that may be dot-notated (e.g. "theme.color_palette").
    Returns _MISSING sentinel if any segment is absent.
    """
    parts = dotted_key.split(".")
    current: Any = obj
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _is_empty(value: Any) -> bool:
    """True for None, empty string, empty list, empty dict."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False
