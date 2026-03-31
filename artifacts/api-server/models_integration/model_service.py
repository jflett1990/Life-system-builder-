"""
ModelService — the single entry point for all model calls in the pipeline.

Responsibilities:
  1. Provider factory: instantiate the correct BaseModelProvider based on config
  2. Expose the three pipeline operations as named methods
  3. Log outcome metadata (was_repaired, from_llm, validation status)
  4. Decide whether to raise OutputValidationError or return a degraded result
     based on strict_validation setting

Pipeline services import ModelService only — they never touch providers directly.

Usage:
    svc = ModelService()
    output = svc.generate_structured_output(prompt, contract)
    validation = svc.validate_output(contract.stage, output.data, contract.required_output_fields)
    preview = svc.generate_preview_text(contract.stage, output.data)
"""
from __future__ import annotations

from typing import Any

from core.config import settings
from core.logging import get_logger
from models_integration.base import BaseModelProvider, StructuredOutput, PreviewText
from models_integration.errors import OutputValidationError
from models_integration.errors import FieldError
from models_integration.output_validator import OutputValidation

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Provider registry — add new providers here
# ---------------------------------------------------------------------------

def _load_provider(name: str) -> BaseModelProvider:
    """
    Instantiate a provider by name.

    Available providers:
      "openai" — OpenAIProvider (default)
    """
    if name == "openai":
        from models_integration.openai_provider import OpenAIProvider
        return OpenAIProvider()
    raise ValueError(
        f"Unknown model_provider '{name}'. "
        "Supported providers: 'openai'"
    )


# Module-level singleton — created once per process
_provider_instance: BaseModelProvider | None = None


def _get_provider() -> BaseModelProvider:
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = _load_provider(settings.model_provider)
        logger.info(
            "ModelService | provider=%s | model=%s | timeout=%ds | retries=%d",
            _provider_instance.provider_name(),
            settings.openai_model,
            settings.model_timeout_s,
            settings.model_max_retries,
        )
    return _provider_instance


# ---------------------------------------------------------------------------
# ModelService
# ---------------------------------------------------------------------------

class ModelService:
    """
    Wrapper used by pipeline services for all model interactions.

    Stateless — safe to instantiate per-request or as a singleton.

    Args:
        strict_validation: If True, raise OutputValidationError when required
                           fields are missing.  If False, log a warning and
                           continue with potentially incomplete data.
                           Default: True (pipeline stages require full output).
    """

    def __init__(self, strict_validation: bool = True) -> None:
        self._provider = _get_provider()
        self._strict = strict_validation

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_structured_output(
        self,
        prompt: Any,     # AssembledPrompt
        contract: Any,   # ContractDefinition
    ) -> StructuredOutput:
        """
        Generate and validate structured JSON for a pipeline stage.

        1. Sends the assembled prompt to the provider
        2. Provider extracts/repairs JSON from the response
        3. Validates required fields (strict or lenient depending on config)
        4. Returns StructuredOutput

        Raises:
          ModelProviderError    — API failure
          ModelOutputError      — unparseable response
          OutputValidationError — missing required fields (if strict_validation)
        """
        output = self._provider.generate_structured_output(prompt, contract)

        if output.was_repaired:
            logger.warning(
                "Stage '%s': JSON required %d repair pass(es) — output may be degraded",
                output.stage, output.repair_attempts,
            )

        # Run structural validation
        validation = self._provider.validate_output(
            stage=output.stage,
            output=output.data,
            required_fields=contract.required_output_fields,
            schema=contract.output_schema,
        )

        if not validation.valid:
            self._handle_validation_failure(output.stage, validation)

        logger.info(
            "Stage '%s' | contract=%s | fields=%d | repaired=%s | valid=%s",
            output.stage,
            output.contract_name,
            len(output.data),
            output.was_repaired,
            validation.valid,
        )

        return output

    def validate_output(
        self,
        stage: str,
        output: dict[str, Any],
        required_fields: list[str],
        schema: dict[str, Any] | None = None,
    ) -> OutputValidation:
        """
        Run structural validation on an existing dict.

        Safe to call independently (e.g. after loading a stored output to
        check it still conforms to an updated contract).

        Returns OutputValidation — never raises.
        """
        result = self._provider.validate_output(stage, output, required_fields, schema)
        if not result.valid:
            logger.debug(
                "validate_output | stage=%s | %s",
                stage, result.error_summary,
            )
        return result

    def generate_preview_text(
        self,
        stage: str,
        output: dict[str, Any],
    ) -> PreviewText:
        """
        Generate a short human-readable summary of stage output.

        Never raises — returns a safe fallback on any error.
        """
        try:
            preview = self._provider.generate_preview_text(stage, output)
            logger.debug(
                "Preview | stage=%s | from_llm=%s | text='%s...'",
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

    def _handle_validation_failure(
        self, stage: str, validation: OutputValidation
    ) -> None:
        if self._strict:
            field_errors = [
                FieldError(field=f, reason="missing") for f in validation.missing_fields
            ] + [
                FieldError(field=f, reason="empty") for f in validation.empty_fields
            ] + [
                FieldError(field=e, reason="wrong_type") for e in validation.type_errors
            ]
            raise OutputValidationError(
                f"Stage '{stage}' output failed structural validation: "
                + validation.error_summary,
                stage=stage,
                field_errors=field_errors,
                output_keys=list(validation.missing_fields + validation.empty_fields),
            )
        else:
            logger.warning(
                "Stage '%s' output validation issues (non-strict): %s",
                stage, validation.error_summary,
            )
