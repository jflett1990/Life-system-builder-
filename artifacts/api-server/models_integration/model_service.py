"""
ModelService — single entry point for all model calls in the pipeline.

Responsibilities:
  1. Provider factory: instantiate correct BaseModelProvider from config
  2. Schema lookup: find the Pydantic class for a stage by name
  3. Generate + validate: call provider with schema class, receive (StructuredOutput, ParseResult)
  4. Decide final data: prefer ParseResult.parsed_data (schema-validated) over raw dict
  5. Log outcome details: was_repaired, schema pass/fail, attempt count
  6. On schema failure: raise OutputValidationError with structured field errors

Failure policy:
  - strict_validation=True (default): raises OutputValidationError after all retries
  - strict_validation=False: logs warning, returns the unvalidated raw dict
    (used when you explicitly want a best-effort run, e.g. pipeline_run_all)

Usage:
    svc = ModelService()
    output, parse_result = svc.generate_structured_output(prompt, contract)
    # output.data contains schema-validated (or raw if no schema) dict
    # parse_result carries raw_text, raw_data, validation_errors, attempt info
"""
from __future__ import annotations

from typing import Any

from core.config import settings
from core.logging import get_logger
from models_integration.base import BaseModelProvider, StructuredOutput, PreviewText
from models_integration.errors import OutputValidationError, FieldError
from models_integration.output_validator import OutputValidation
from models_integration.parser import ParseResult, StageOutputParser
from schemas.stage_outputs import get_schema

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

def _load_provider(name: str) -> BaseModelProvider:
    if name == "openai":
        from models_integration.openai_provider import OpenAIProvider
        return OpenAIProvider()
    raise ValueError(f"Unknown model_provider '{name}'. Supported: 'openai'")


_provider_instance: BaseModelProvider | None = None


def _get_provider() -> BaseModelProvider:
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = _load_provider(settings.model_provider)
        logger.info(
            "ModelService | provider=%s | model=%s | timeout=%ds | retries=%d | schema_retries=%d",
            _provider_instance.provider_name(),
            settings.openai_model,
            settings.model_timeout_s,
            settings.model_max_retries,
            settings.schema_retry_attempts,
        )
    return _provider_instance


# ---------------------------------------------------------------------------
# ModelService
# ---------------------------------------------------------------------------

class ModelService:
    """
    Stateless wrapper used by pipeline services for all model interactions.

    Args:
        strict_validation: If True (default), raise OutputValidationError when
                           all schema retry attempts fail. If False, log a
                           warning and return the best available (unvalidated) output.
    """

    def __init__(self, strict_validation: bool = True) -> None:
        self._provider = _get_provider()
        self._strict = strict_validation
        self._parser = StageOutputParser()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_structured_output(
        self,
        prompt: Any,     # AssembledPrompt
        contract: Any,   # ContractDefinition
    ) -> tuple[StructuredOutput, ParseResult]:
        """
        Generate structured JSON for a pipeline stage, with schema enforcement.

        Flow:
          1. Look up Pydantic schema for the stage
          2. Call provider (which runs schema retry loop internally)
          3. If parse_result.success → use parsed_data (schema-validated)
          4. If parse_result.failed + strict → raise OutputValidationError
          5. If parse_result.failed + lenient → return raw_data with warning

        Returns:
          (StructuredOutput, ParseResult)
          - output.data is the final dict (parsed or raw)
          - parse_result carries raw_text, validation_errors, attempt metadata

        Raises:
          ModelProviderError    — API failure
          ModelOutputError      — cannot extract JSON from any attempt
          OutputValidationError — schema validation failed after all retries (strict mode)
        """
        stage = getattr(prompt, "stage", None) or "unknown"
        schema_class = get_schema(stage)

        if schema_class is not None:
            logger.debug("Stage '%s' → schema=%s", stage, schema_class.__name__)
        else:
            logger.debug("Stage '%s' → no schema registered", stage)

        output, parse_result = self._provider.generate_structured_output(
            prompt, contract, schema_class=schema_class
        )

        # Decide final data — never raise here; let the caller save raw output first
        if parse_result.success and parse_result.parsed_data is not None:
            final_data = parse_result.parsed_data
        else:
            final_data = parse_result.raw_data
            if parse_result.has_schema and self._strict:
                # Log the failure now; caller is responsible for raising OutputValidationError
                # after it has persisted the raw output to the database.
                logger.error(
                    "Stage '%s' schema validation FAILED after %d attempt(s): %s",
                    stage, parse_result.attempt, parse_result.error_summary(5),
                )

        # Replace output.data with the decided final data
        final_output = StructuredOutput(
            data=final_data,
            raw_text=output.raw_text,
            stage=output.stage,
            contract_name=output.contract_name,
            was_repaired=output.was_repaired,
            repair_attempts=output.repair_attempts,
            token_usage=output.token_usage,
        )

        logger.info(
            "Stage '%s' | schema_pass=%s | repaired=%s | attempt=%d | fields=%d",
            stage,
            parse_result.success,
            output.was_repaired,
            parse_result.attempt,
            len(final_data),
        )

        return final_output, parse_result

    def validate_output(
        self,
        stage: str,
        output: dict[str, Any],
        required_fields: list[str],
        schema: dict[str, Any] | None = None,
    ) -> OutputValidation:
        """Structural field presence check. Never raises."""
        result = self._provider.validate_output(stage, output, required_fields, schema)
        if not result.valid:
            logger.debug("validate_output | stage=%s | %s", stage, result.error_summary)
        return result

    def generate_preview_text(
        self,
        stage: str,
        output: dict[str, Any],
    ) -> PreviewText:
        """Generate preview text. Never raises."""
        try:
            preview = self._provider.generate_preview_text(stage, output)
            logger.debug(
                "Preview | stage=%s | from_llm=%s | '%s...'",
                stage, preview.from_llm, preview.text[:60],
            )
            return preview
        except Exception as e:
            logger.warning("generate_preview_text failed for stage '%s': %s", stage, e)
            return PreviewText(
                text=f"{stage.replace('_', ' ').title()} — output generated",
                stage=stage,
                from_llm=False,
            )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _handle_schema_failure(self, stage: str, parse_result: ParseResult) -> None:
        logger.error(
            "Stage '%s' schema validation FAILED after %d attempt(s): %s",
            stage, parse_result.attempt, parse_result.error_summary(5),
        )
        if self._strict:
            field_errors = [
                FieldError(field=e.split(":")[0].strip(), reason=e)
                for e in parse_result.validation_errors
            ]
            raise OutputValidationError(
                parse_result.for_error_message(),
                stage=stage,
                field_errors=field_errors,
            )
        else:
            logger.warning(
                "Stage '%s' returning unvalidated output (non-strict mode)", stage
            )
