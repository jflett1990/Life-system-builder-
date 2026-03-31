"""
OpenAIProvider — concrete implementation of BaseModelProvider for OpenAI.

Handles:
  - Client initialisation (api_key, base_url, timeout)
  - Retry logic for transient API errors (rate limits, 5xx)
  - JSON extraction with progressive fallback strategies
  - One-shot repair pass for malformed JSON responses
  - Structural output validation after successful parse
  - Lightweight preview text generation (heuristic-first, LLM-fallback)

Error hierarchy:
  ModelProviderError  ← openai.RateLimitError, openai.APIError, timeout
  ModelOutputError    ← JSON parse / extraction failure after all repairs
  OutputValidationError ← parsed but required fields missing (raised only when
                          strict_validation=True on the service; provider
                          returns OutputValidation so callers decide)
"""
from __future__ import annotations

import time
from typing import Any

from openai import OpenAI, RateLimitError, APIError, APITimeoutError

from core.config import settings
from core.logging import get_logger
from models_integration.base import BaseModelProvider, StructuredOutput, PreviewText
from models_integration.errors import ModelProviderError, ModelOutputError
from models_integration.json_repair import extract_json, repair_json, looks_like_json
from models_integration.output_validator import OutputValidator, OutputValidation

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Preview heuristics: per-stage field priority lists
# ---------------------------------------------------------------------------

_PREVIEW_FIELDS: dict[str, list[str]] = {
    "system_architecture": [
        "systemName", "system_name", "operatingPremise", "systemObjective",
    ],
    "worksheet_system": [
        "summary", "worksheetCount", "worksheet_count",
    ],
    "layout_mapping": [
        "summary", "totalPages", "total_pages", "layoutSummary",
    ],
    "render_blueprint": [
        "summary", "documentTitle", "document_title", "systemName",
    ],
    "validation_audit": [
        "verdict", "summary", "overallVerdict",
    ],
}

_GENERIC_PREVIEW_FIELDS = [
    "systemName", "system_name", "summary", "title", "objective",
    "operatingPremise", "verdict",
]

# Max chars for a preview line
_PREVIEW_MAX_CHARS = 200


class OpenAIProvider(BaseModelProvider):
    """
    OpenAI-backed model provider.

    Reads configuration from Settings:
      - openai_model          model identifier (default: gpt-5.2)
      - model_max_retries     API error retries before giving up (default: 3)
      - model_timeout_s       per-request timeout in seconds (default: 120)
      - model_repair_attempts JSON repair retries (default: 1)
    """

    def __init__(self) -> None:
        self._model = settings.openai_model
        self._max_retries = settings.model_max_retries
        self._timeout = settings.model_timeout_s
        self._repair_attempts = settings.model_repair_attempts
        self._validator = OutputValidator()
        self._client = self._build_client()

    # ── Core generation ───────────────────────────────────────────────────────

    def generate_structured_output(
        self,
        prompt: Any,           # AssembledPrompt
        contract: Any,         # ContractDefinition
    ) -> StructuredOutput:
        """
        Send assembled prompt to OpenAI, parse JSON, validate required fields.

        Retry loop:
          - Up to model_max_retries on RateLimitError / APIError
          - Exponential backoff: 2^attempt seconds (capped at 30s)

        JSON repair:
          - On parse failure, attempt extract_json with all strategies
          - If that fails, send a repair prompt and retry once

        Returns StructuredOutput with was_repaired=True if any repair was needed.
        """
        messages = prompt.to_openai_messages()
        stage = prompt.stage or "unknown"
        contract_name = prompt.contract_name

        logger.info(
            "ModelProvider | generate_structured_output | model=%s stage=%s contract=%s",
            self._model, stage, contract_name,
        )

        raw_text = self._call_with_retry(
            messages=messages,
            stage=stage,
            contract_name=contract_name,
        )

        # Attempt primary extraction
        was_repaired = False
        repair_count = 0

        try:
            data = extract_json(
                raw_text,
                output_mode=prompt.output_mode,
                stage=stage,
                contract_name=contract_name,
            )
        except ModelOutputError as primary_error:
            # One-shot LLM repair pass
            data, was_repaired, repair_count = self._attempt_llm_repair(
                raw_text=raw_text,
                stage=stage,
                contract_name=contract_name,
                original_error=primary_error,
            )

        # Token usage (best-effort — not all endpoints expose this)
        token_usage: dict[str, int] = {}

        return StructuredOutput(
            data=data,
            raw_text=raw_text,
            stage=stage,
            contract_name=contract_name,
            was_repaired=was_repaired,
            repair_attempts=repair_count,
            token_usage=token_usage,
        )

    def validate_output(
        self,
        stage: str,
        output: dict[str, Any],
        required_fields: list[str],
        schema: dict[str, Any] | None = None,
    ) -> OutputValidation:
        """
        Structural validation — no model call.

        Delegates to OutputValidator which checks required fields and
        JSON Schema type hints.
        """
        return self._validator.validate(stage, output, required_fields, schema)

    def generate_preview_text(
        self,
        stage: str,
        output: dict[str, Any],
    ) -> PreviewText:
        """
        Generate a one-line preview.

        Strategy:
          1. Try stage-specific known fields → instant, no LLM call
          2. Try generic fields → instant, no LLM call
          3. Fall back to a short LLM summarise call (never raises)
        """
        # Stage-specific heuristic
        for field_name in _PREVIEW_FIELDS.get(stage, []):
            value = output.get(field_name)
            if isinstance(value, str) and value.strip():
                return PreviewText(
                    text=value.strip()[:_PREVIEW_MAX_CHARS],
                    stage=stage,
                    from_llm=False,
                )

        # Generic heuristic
        for field_name in _GENERIC_PREVIEW_FIELDS:
            value = output.get(field_name)
            if isinstance(value, str) and value.strip():
                return PreviewText(
                    text=value.strip()[:_PREVIEW_MAX_CHARS],
                    stage=stage,
                    from_llm=False,
                )

        # Count-based fallback for array-heavy outputs
        top_keys = list(output.keys())[:6]
        if top_keys:
            return PreviewText(
                text=f"Output: {', '.join(top_keys)}",
                stage=stage,
                from_llm=False,
            )

        # LLM fallback — never raises
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
            # SDK-level retries disabled — we manage our own loop for observability
            "max_retries": 0,
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
        """
        Call OpenAI chat completions with exponential-backoff retry.

        Returns raw text from the model.
        Raises ModelProviderError after all retries exhausted.
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,  # type: ignore[arg-type]
                    max_completion_tokens=8192,
                )
                content = response.choices[0].message.content or ""
                logger.debug(
                    "OpenAI response | stage=%s attempt=%d len=%d",
                    stage, attempt, len(content),
                )
                return content

            except RateLimitError as e:
                last_error = e
                wait = min(2 ** attempt, 30)
                logger.warning(
                    "Rate limit on attempt %d/%d for stage '%s' — waiting %ds",
                    attempt + 1, self._max_retries, stage, wait,
                )
                time.sleep(wait)

            except APITimeoutError as e:
                last_error = e
                logger.warning(
                    "Timeout on attempt %d/%d for stage '%s'",
                    attempt + 1, self._max_retries, stage,
                )
                # Timeouts are retriable
                if attempt < self._max_retries - 1:
                    time.sleep(2 ** attempt)

            except APIError as e:
                last_error = e
                logger.error(
                    "APIError on attempt %d/%d for stage '%s': %s",
                    attempt + 1, self._max_retries, stage, e,
                )
                # 4xx errors (except 429 / rate limit) are not retriable
                if hasattr(e, "status_code") and e.status_code and 400 <= e.status_code < 500:
                    break
                if attempt < self._max_retries - 1:
                    time.sleep(2 ** attempt)

        status_code = getattr(last_error, "status_code", None)
        raise ModelProviderError(
            f"OpenAI API failed for stage '{stage}' after {self._max_retries} attempt(s): {last_error}",
            provider="openai",
            status_code=status_code,
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
        """
        Ask the model to repair its own malformed response.

        Sends a short correction prompt with the bad response and asks for
        valid JSON only.  Only attempted once.

        Returns (data, was_repaired=True, repair_count=1) on success.
        Raises ModelOutputError if repair also fails.
        """
        logger.warning(
            "JSON parse failed for stage '%s' — attempting LLM repair (1 pass)",
            stage,
        )

        # First try local repair strategies before calling the model
        local_repair = repair_json(raw_text, stage=stage, contract_name=contract_name)
        if local_repair is not None:
            logger.info("Local JSON repair succeeded for stage '%s'", stage)
            return local_repair, True, 1

        repair_messages = [
            {
                "role": "system",
                "content": (
                    "You are a JSON repair assistant. The user will send you a malformed "
                    "JSON response. You must return ONLY a valid, complete JSON object "
                    "with no markdown fences, no prose, and no explanations. "
                    "Fix any syntax errors. Do not add or remove semantic content."
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
                messages=repair_messages,
                stage=f"{stage}_repair",
                contract_name=contract_name,
            )
            data = extract_json(
                repaired_text,
                output_mode="json",
                stage=stage,
                contract_name=contract_name,
            )
            logger.info("LLM repair succeeded for stage '%s'", stage)
            return data, True, 1

        except (ModelProviderError, ModelOutputError) as repair_error:
            logger.error(
                "LLM repair also failed for stage '%s': %s",
                stage, repair_error,
            )
            raise ModelOutputError(
                f"JSON extraction failed and repair also failed for stage '{stage}'",
                stage=stage,
                contract_name=contract_name,
                raw_text=raw_text,
                parse_error=str(original_error),
                repair_attempted=True,
            ) from repair_error

    def _llm_preview_fallback(self, stage: str, output: dict[str, Any]) -> PreviewText:
        """
        Last-resort: ask the model for a one-line summary.

        Never raises — returns a safe default on any failure.
        """
        import json as _json
        try:
            preview_messages = [
                {
                    "role": "system",
                    "content": (
                        "You summarise structured data in one sentence (max 150 characters). "
                        "Return only the sentence — no quotes, no punctuation at the end."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Summarise this stage output for '{stage}' in one sentence:\n"
                        + _json.dumps(output, indent=2)[:1500]
                    ),
                },
            ]
            response = self._client.chat.completions.create(
                model=self._model,
                messages=preview_messages,  # type: ignore[arg-type]
                max_completion_tokens=80,
            )
            text = (response.choices[0].message.content or "").strip()[:_PREVIEW_MAX_CHARS]
            return PreviewText(text=text, stage=stage, from_llm=True)
        except Exception as e:
            logger.debug("Preview LLM fallback failed for stage '%s': %s", stage, e)
            return PreviewText(
                text=f"{stage.replace('_', ' ').title()} output generated",
                stage=stage,
                from_llm=False,
            )
