"""
OpenAIProvider — concrete implementation of BaseModelProvider for OpenAI.

Handles:
  - Client initialisation (api_key, base_url, timeout)
  - Retry logic for transient API errors (rate limits, 5xx)
  - JSON extraction with progressive fallback strategies
  - One-shot LLM repair pass for malformed JSON
  - Pydantic schema validation with up to N correction retry passes
  - Lightweight preview text generation (heuristic-first, LLM-fallback)

Retry layers (innermost to outermost):
  1. API transport retries    — _call_with_retry (up to model_max_retries)
  2. JSON repair pass         — _attempt_llm_repair (1 extra call if JSON is bad)
  3. Schema correction passes — generate_structured_output schema retry loop (up to schema_retry_attempts)

Error hierarchy:
  ModelProviderError  ← openai API-level errors (rate limit, timeout, auth)
  ModelOutputError    ← JSON extraction failed after all repair strategies
  OutputValidationError is NOT raised here; it's raised by ModelService after receiving ParseResult
"""
from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel
from openai import OpenAI, RateLimitError, APIError, APITimeoutError

from core.config import settings
from core.logging import get_logger
from models_integration.base import BaseModelProvider, StructuredOutput, PreviewText
from models_integration.errors import ModelProviderError, ModelOutputError
from models_integration.json_repair import extract_json, repair_json
from models_integration.output_validator import OutputValidator, OutputValidation
from models_integration.parser import StageOutputParser, ParseResult

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Preview heuristics: per-stage field priority lists
# ---------------------------------------------------------------------------

_PREVIEW_FIELDS: dict[str, list[str]] = {
    "system_architecture": [
        "system_name", "systemName", "operating_premise", "system_objective",
    ],
    "worksheet_system": [
        "worksheet_system_name", "worksheetSystemName",
    ],
    "layout_mapping": [
        "document_title", "documentTitle",
    ],
    "render_blueprint": [
        "blueprint_name", "blueprintName",
    ],
    "validation_audit": [
        "audit_summary", "auditSummary",
    ],
}

_GENERIC_PREVIEW_FIELDS = [
    "system_name", "systemName", "document_title", "summary",
    "title", "objective", "operating_premise", "verdict",
]

_PREVIEW_MAX_CHARS = 200


class OpenAIProvider(BaseModelProvider):
    """
    OpenAI-backed model provider.

    Config (from Settings):
      openai_model          — model identifier (default: gpt-5.2)
      model_max_retries     — API error retries (default: 3)
      model_timeout_s       — per-request timeout in seconds (default: 120)
      model_repair_attempts — JSON repair retries (default: 1)
      schema_retry_attempts — Pydantic schema failure retries (default: 2)
    """

    def __init__(self) -> None:
        self._model = settings.openai_model
        self._max_retries = settings.model_max_retries
        self._timeout = settings.model_timeout_s
        self._repair_attempts = settings.model_repair_attempts
        self._schema_retry_attempts = settings.schema_retry_attempts
        self._validator = OutputValidator()
        self._parser = StageOutputParser()
        self._client = self._build_client()

    # ── Core generation ───────────────────────────────────────────────────────

    def generate_structured_output(
        self,
        prompt: Any,                         # AssembledPrompt
        contract: Any,                       # ContractDefinition
        schema_class: type[BaseModel] | None = None,
    ) -> tuple[StructuredOutput, ParseResult]:
        """
        Call OpenAI, extract JSON, optionally validate against Pydantic schema.

        Returns a (StructuredOutput, ParseResult) tuple.

        Schema retry loop:
          - Attempt 1: normal generation
          - On Pydantic failure: build correction conversation → retry
          - Up to schema_retry_attempts additional calls

        Raises:
          ModelProviderError — API failure (after all retries)
          ModelOutputError   — Cannot extract JSON from any response
        """
        stage = prompt.stage or "unknown"
        contract_name = prompt.contract_name
        messages = prompt.to_openai_messages()

        logger.info(
            "ModelProvider | generate_structured_output | model=%s stage=%s",
            self._model, stage,
        )

        last_parse_result: ParseResult | None = None
        was_repaired = False
        repair_count = 0

        for schema_attempt in range(self._schema_retry_attempts + 1):
            # --- Transport + JSON extraction ---
            if schema_attempt == 0:
                raw_text = self._call_with_retry(
                    messages, stage=stage, contract_name=contract_name
                )
            else:
                # Subsequent attempts use the correction conversation
                assert last_parse_result is not None
                correction_messages = self._build_correction_messages(
                    original_messages=messages,
                    parse_result=last_parse_result,
                )
                logger.info(
                    "Schema correction pass %d/%d for stage '%s' — %d error(s)",
                    schema_attempt, self._schema_retry_attempts,
                    stage, len(last_parse_result.validation_errors),
                )
                raw_text = self._call_with_retry(
                    correction_messages,
                    stage=f"{stage}_schema_fix_{schema_attempt}",
                    contract_name=contract_name,
                )

            # --- JSON extraction ---
            try:
                data = extract_json(
                    raw_text,
                    output_mode=prompt.output_mode,
                    stage=stage,
                    contract_name=contract_name,
                )
            except ModelOutputError as primary_err:
                data, was_repaired, repair_count = self._attempt_llm_repair(
                    raw_text=raw_text,
                    stage=stage,
                    contract_name=contract_name,
                    original_error=primary_err,
                )

            # --- Schema validation ---
            if schema_class is not None:
                parse_result = self._parser.parse(
                    stage=stage,
                    data=data,
                    raw_text=raw_text,
                    attempt=schema_attempt + 1,
                )
                last_parse_result = parse_result

                if parse_result.success:
                    logger.info(
                        "Stage '%s' | schema PASS on attempt %d",
                        stage, schema_attempt + 1,
                    )
                    break  # Success — use this data

                if schema_attempt < self._schema_retry_attempts:
                    logger.warning(
                        "Stage '%s' | schema FAIL on attempt %d — will retry | errors: %s",
                        stage, schema_attempt + 1, parse_result.error_summary(3),
                    )
                    continue  # Loop to retry

                # All schema retries exhausted — return the failure result
                logger.error(
                    "Stage '%s' | schema FAIL after %d attempt(s) — all retries exhausted",
                    stage, self._schema_retry_attempts + 1,
                )
                break

            else:
                # No schema registered — skip Pydantic, create a pass-through ParseResult
                parse_result = self._parser.parse(
                    stage=stage, data=data, raw_text=raw_text, attempt=schema_attempt + 1
                )
                last_parse_result = parse_result
                break

        assert last_parse_result is not None
        output = StructuredOutput(
            data=last_parse_result.raw_data,   # Always raw_data; service uses parsed_data
            raw_text=raw_text,
            stage=stage,
            contract_name=contract_name,
            was_repaired=was_repaired,
            repair_attempts=repair_count,
        )
        return output, last_parse_result

    def validate_output(
        self,
        stage: str,
        output: dict[str, Any],
        required_fields: list[str],
        schema: dict[str, Any] | None = None,
    ) -> OutputValidation:
        return self._validator.validate(stage, output, required_fields, schema)

    def generate_preview_text(
        self,
        stage: str,
        output: dict[str, Any],
    ) -> PreviewText:
        for field_name in _PREVIEW_FIELDS.get(stage, []):
            value = output.get(field_name)
            if isinstance(value, str) and value.strip():
                return PreviewText(text=value.strip()[:_PREVIEW_MAX_CHARS], stage=stage, from_llm=False)

        for field_name in _GENERIC_PREVIEW_FIELDS:
            value = output.get(field_name)
            if isinstance(value, str) and value.strip():
                return PreviewText(text=value.strip()[:_PREVIEW_MAX_CHARS], stage=stage, from_llm=False)

        top_keys = list(output.keys())[:6]
        if top_keys:
            return PreviewText(text=f"Output: {', '.join(top_keys)}", stage=stage, from_llm=False)

        return self._llm_preview_fallback(stage, output)

    def provider_name(self) -> str:
        return f"openai:{self._model}"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_client(self) -> OpenAI:
        api_key = settings.get_openai_api_key()
        base_url = settings.get_openai_base_url()
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": float(self._timeout),
            "max_retries": 0,  # SDK retries off; we manage our own loop
        }
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAI(**kwargs)

    def _call_with_retry(
        self,
        messages: list[dict[str, str]],
        *,
        stage: str,
        contract_name: str,
    ) -> str:
        """Exponential-backoff retry on transport-level errors."""
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,  # type: ignore[arg-type]
                )
                choice = response.choices[0]
                finish_reason = choice.finish_reason or "unknown"
                # Reasoning models (o1/o3 family) may return content=None when the
                # completion_token budget is exhausted by internal reasoning steps.
                # Fall back to empty string; caller will handle the parse failure.
                content = choice.message.content or ""
                logger.info(
                    "OpenAI response | stage=%s attempt=%d len=%d finish_reason=%s",
                    stage, attempt, len(content), finish_reason,
                )
                return content

            except RateLimitError as e:
                last_error = e
                wait = min(2 ** attempt, 30)
                logger.warning(
                    "Rate limit | attempt %d/%d | stage='%s' | waiting %ds",
                    attempt + 1, self._max_retries, stage, wait,
                )
                time.sleep(wait)

            except APITimeoutError as e:
                last_error = e
                logger.warning("Timeout | attempt %d/%d | stage='%s'", attempt + 1, self._max_retries, stage)
                if attempt < self._max_retries - 1:
                    time.sleep(2 ** attempt)

            except APIError as e:
                last_error = e
                logger.error("APIError | attempt %d/%d | stage='%s': %s", attempt + 1, self._max_retries, stage, e)
                if hasattr(e, "status_code") and e.status_code and 400 <= e.status_code < 500:
                    break
                if attempt < self._max_retries - 1:
                    time.sleep(2 ** attempt)

        raise ModelProviderError(
            f"OpenAI API failed for stage '{stage}' after {self._max_retries} attempt(s): {last_error}",
            provider="openai",
            status_code=getattr(last_error, "status_code", None),
            retries_exhausted=True,
        )

    def _attempt_llm_repair(
        self,
        *,
        raw_text: str,
        stage: str,
        contract_name: str,
        original_error: ModelOutputError,
    ) -> tuple[dict[str, Any], bool, int]:
        """Ask the model to repair its own malformed JSON (one pass)."""
        logger.warning("JSON parse failed for stage '%s' — attempting repair", stage)

        from models_integration.json_repair import repair_json
        local_repair = repair_json(raw_text, stage=stage, contract_name=contract_name)
        if local_repair is not None:
            logger.info("Local JSON repair succeeded for stage '%s'", stage)
            return local_repair, True, 1

        repair_messages = [
            {
                "role": "system",
                "content": (
                    "You are a JSON repair assistant. The user will send you a malformed "
                    "JSON response. Return ONLY a valid, complete JSON object — "
                    "no markdown, no prose, no code fences. Fix syntax errors only. "
                    "Do not add or remove semantic content."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"The following response for stage '{stage}' is malformed JSON. "
                    f"Please fix and return only valid JSON:\n\n{raw_text[:3000]}"
                ),
            },
        ]

        try:
            repaired_text = self._call_with_retry(
                repair_messages, stage=f"{stage}_repair", contract_name=contract_name
            )
            data = extract_json(repaired_text, output_mode="json", stage=stage, contract_name=contract_name)
            logger.info("LLM repair succeeded for stage '%s'", stage)
            return data, True, 1
        except (ModelProviderError, ModelOutputError) as repair_error:
            logger.error("LLM repair also failed for stage '%s': %s", stage, repair_error)
            raise ModelOutputError(
                f"JSON extraction + repair both failed for stage '{stage}'",
                stage=stage,
                contract_name=contract_name,
                raw_text=raw_text,
                parse_error=str(original_error),
                repair_attempted=True,
            ) from repair_error

    def _build_correction_messages(
        self,
        original_messages: list[dict[str, str]],
        parse_result: ParseResult,
    ) -> list[dict[str, str]]:
        """
        Build a correction conversation:
          [original system] + [original user] + [bad assistant response] + [correction user]

        The correction user message tells the model exactly which fields failed.
        Uses the parsed/repaired dict (not the raw broken text) as the assistant content
        so the model sees a clean JSON representation, not its malformed original output.
        """
        import json as _json

        # Prefer the extracted dict over the (possibly broken) raw text for the
        # assistant turn — this is what the parser actually read, so it's coherent.
        if parse_result.raw_data:
            try:
                assistant_content = _json.dumps(parse_result.raw_data, indent=2)[:4000]
            except Exception:
                assistant_content = parse_result.raw_text[:4000]
        else:
            assistant_content = parse_result.raw_text[:4000]

        correction_user = parse_result.for_retry_prompt()
        return [
            *original_messages,
            {"role": "assistant", "content": assistant_content},
            {"role": "user", "content": correction_user},
        ]

    def _llm_preview_fallback(self, stage: str, output: dict[str, Any]) -> PreviewText:
        import json as _json
        try:
            preview_messages = [
                {"role": "system", "content": "Summarise structured data in one sentence (max 150 chars). Return only the sentence."},
                {"role": "user", "content": f"Summarise this '{stage}' output:\n" + _json.dumps(output, indent=2)[:1500]},
            ]
            response = self._client.chat.completions.create(
                model=self._model, messages=preview_messages,  # type: ignore[arg-type]
                max_completion_tokens=80,
            )
            text = (response.choices[0].message.content or "").strip()[:_PREVIEW_MAX_CHARS]
            return PreviewText(text=text, stage=stage, from_llm=True)
        except Exception as e:
            logger.debug("Preview LLM fallback failed for stage '%s': %s", stage, e)
            return PreviewText(text=f"{stage.replace('_', ' ').title()} output generated", stage=stage, from_llm=False)
