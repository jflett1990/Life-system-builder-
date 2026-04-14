"""
AnthropicProvider — concrete implementation of BaseModelProvider for Anthropic Claude.

Mirrors the structure of OpenAIProvider but uses the Anthropic Python SDK.

Key differences from OpenAI:
  - system message is passed as a top-level `system` kwarg, not in messages list
  - Response text is at response.content[0].text
  - Token kwarg is `max_tokens` (required), not `max_completion_tokens`
  - Error types: anthropic.RateLimitError, anthropic.APIError, anthropic.APITimeoutError
"""
from __future__ import annotations

import os
import time
from typing import Any

from pydantic import BaseModel
import anthropic

from core.config import settings
from core.logging import get_logger
from models_integration.base import BaseModelProvider, StructuredOutput, PreviewText
from models_integration.errors import ModelProviderError, ModelOutputError
from models_integration.json_repair import extract_json, repair_json
from models_integration.output_validator import OutputValidator, OutputValidation
from models_integration.parser import StageOutputParser, ParseResult

logger = get_logger(__name__)

_PREVIEW_FIELDS: dict[str, list[str]] = {
    "system_architecture": ["system_name", "operating_premise", "system_objective"],
    "worksheet_system": ["worksheet_system_name"],
    "layout_mapping": ["document_title"],
    "render_blueprint": ["blueprint_name"],
    "validation_audit": ["audit_summary"],
}

_GENERIC_PREVIEW_FIELDS = [
    "system_name", "document_title", "summary", "title",
    "objective", "operating_premise", "verdict",
]

_PREVIEW_MAX_CHARS = 200

# Max tokens to request from the model. Claude supports up to 32k output tokens
# for most models; 16k is a safe ceiling for pipeline stages.
_MAX_OUTPUT_TOKENS = 32000


class AnthropicProvider(BaseModelProvider):
    """
    Anthropic Claude-backed model provider.

    Reads ANTHROPIC_API_KEY from environment (falls back to settings).
    Model selection mirrors OpenAIProvider: model_override → planner/executor model.
    """

    def __init__(self) -> None:
        self._default_model = settings.executor_model
        self._max_retries = settings.model_max_retries
        self._timeout = settings.model_timeout_s
        self._repair_attempts = settings.model_repair_attempts
        self._schema_retry_attempts = settings.schema_retry_attempts
        self._validator = OutputValidator()
        self._parser = StageOutputParser()
        # Client is built lazily per-call so token refreshes are always picked up
        self._client: anthropic.Anthropic | None = None

    # ── Core generation ───────────────────────────────────────────────────────

    def generate_structured_output(
        self,
        prompt: Any,
        contract: Any,
        schema_class: type[BaseModel] | None = None,
        model_override: str | None = None,
    ) -> tuple[StructuredOutput, ParseResult]:
        stage = prompt.stage or "unknown"
        contract_name = prompt.contract_name
        active_model = model_override or self._default_model

        # Split system vs user messages
        msgs = prompt.to_openai_messages()
        system_msg = next((m["content"] for m in msgs if m["role"] == "system"), "")
        user_msgs = [m for m in msgs if m["role"] != "system"]

        logger.info(
            "AnthropicProvider | generate_structured_output | model=%s stage=%s",
            active_model, stage,
        )

        last_parse_result: ParseResult | None = None
        was_repaired = False
        repair_count = 0
        raw_text = ""

        for schema_attempt in range(self._schema_retry_attempts + 1):
            if schema_attempt == 0:
                raw_text = self._call_with_retry(
                    system=system_msg,
                    messages=user_msgs,
                    stage=stage,
                    contract_name=contract_name,
                    model=active_model,
                )
            else:
                assert last_parse_result is not None
                correction_messages = self._build_correction_messages(
                    original_user_msgs=user_msgs,
                    parse_result=last_parse_result,
                )
                logger.info(
                    "Schema correction pass %d/%d for stage '%s' — %d error(s)",
                    schema_attempt, self._schema_retry_attempts,
                    stage, len(last_parse_result.validation_errors),
                )
                raw_text = self._call_with_retry(
                    system=system_msg,
                    messages=correction_messages,
                    stage=f"{stage}_schema_fix_{schema_attempt}",
                    contract_name=contract_name,
                    model=active_model,
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
                    system=system_msg,
                    stage=stage,
                    contract_name=contract_name,
                    original_error=primary_err,
                    model=active_model,
                )

            # --- Schema validation ---
            if schema_class is not None:
                parse_result = self._parser.parse(
                    stage=stage,
                    data=data,
                    raw_text=raw_text,
                    attempt=schema_attempt + 1,
                    schema_class=schema_class,
                )
                last_parse_result = parse_result

                if parse_result.success:
                    logger.info("Stage '%s' | schema PASS on attempt %d", stage, schema_attempt + 1)
                    break

                if schema_attempt < self._schema_retry_attempts:
                    logger.warning(
                        "Stage '%s' | schema FAIL on attempt %d — will retry | errors: %s",
                        stage, schema_attempt + 1, parse_result.error_summary(3),
                    )
                    continue

                logger.error(
                    "Stage '%s' | schema FAIL after %d attempt(s) — retries exhausted",
                    stage, self._schema_retry_attempts + 1,
                )
                break

            else:
                parse_result = self._parser.parse(
                    stage=stage, data=data, raw_text=raw_text, attempt=schema_attempt + 1
                )
                last_parse_result = parse_result
                break

        assert last_parse_result is not None
        output = StructuredOutput(
            data=last_parse_result.raw_data,
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

    def generate_preview_text(self, stage: str, output: dict[str, Any]) -> PreviewText:
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

        return PreviewText(text=f"{stage.replace('_', ' ').title()} output generated", stage=stage, from_llm=False)

    def provider_name(self) -> str:
        return f"anthropic:{self._default_model}"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_client(self) -> anthropic.Anthropic:
        """Rebuild client on every call so token refreshes are always used."""
        return self._build_client()

    def _build_client(self) -> anthropic.Anthropic:
        # pydantic_settings loads .env into the Settings object but not os.environ,
        # so we read the key here from the settings helper.
        key = settings.get_anthropic_api_key()
        base_url = settings.get_anthropic_base_url()
        kwargs: dict = {
            "base_url": base_url,
            "timeout": float(self._timeout),
            "max_retries": 0,  # We manage retries ourselves
        }
        # Session ingress tokens (sk-ant-si-...) use Bearer auth, not x-api-key.
        # Regular API keys (sk-ant-api0...) use x-api-key.
        if key.startswith("sk-ant-si-"):
            kwargs["auth_token"] = key
        else:
            kwargs["api_key"] = key
        return anthropic.Anthropic(**kwargs)

    def _call_with_retry(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        stage: str,
        contract_name: str,
        model: str,
    ) -> str:
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = self._get_client().messages.create(
                    model=model,
                    system=system,
                    messages=messages,  # type: ignore[arg-type]
                    max_tokens=_MAX_OUTPUT_TOKENS,
                )
                content = response.content[0].text if response.content else ""
                logger.info(
                    "Anthropic response | stage=%s attempt=%d len=%d stop_reason=%s",
                    stage, attempt, len(content), response.stop_reason,
                )
                return content

            except anthropic.RateLimitError as e:
                last_error = e
                # Rate limits need a full token-window reset (~60s per window).
                # Use 30s, 60s, 90s rather than the fast 1/2/4s exponential.
                wait = 30 * (attempt + 1)
                logger.warning(
                    "Rate limit | attempt %d/%d | stage='%s' | waiting %ds",
                    attempt + 1, self._max_retries, stage, wait,
                )
                time.sleep(wait)

            except anthropic.APITimeoutError as e:
                last_error = e
                logger.warning("Timeout | attempt %d/%d | stage='%s'", attempt + 1, self._max_retries, stage)
                if attempt < self._max_retries - 1:
                    time.sleep(2 ** attempt)

            except anthropic.APIError as e:
                last_error = e
                logger.error("APIError | attempt %d/%d | stage='%s': %s", attempt + 1, self._max_retries, stage, e)
                status = getattr(e, "status_code", None)
                if status and 400 <= status < 500 and status != 429:
                    break
                if attempt < self._max_retries - 1:
                    time.sleep(2 ** attempt)

        raise ModelProviderError(
            f"Anthropic API failed for stage '{stage}' after {self._max_retries} attempt(s): {last_error}",
            provider="anthropic",
            status_code=getattr(last_error, "status_code", None),
            retries_exhausted=True,
        )

    def _attempt_llm_repair(
        self,
        *,
        raw_text: str,
        system: str,
        stage: str,
        contract_name: str,
        original_error: ModelOutputError,
        model: str,
    ) -> tuple[dict[str, Any], bool, int]:
        logger.warning("JSON parse failed for stage '%s' — attempting repair", stage)

        local_repair = repair_json(raw_text, stage=stage, contract_name=contract_name)
        if local_repair is not None:
            logger.info("Local JSON repair succeeded for stage '%s'", stage)
            return local_repair, True, 1

        repair_system = (
            "You are a JSON repair assistant. Return ONLY a valid, complete JSON object — "
            "no markdown, no prose, no code fences. Fix syntax errors only. "
            "Do not add or remove semantic content."
        )
        repair_messages = [
            {
                "role": "user",
                "content": (
                    f"The following response for stage '{stage}' is malformed JSON. "
                    f"Please fix and return only valid JSON:\n\n{raw_text[:3000]}"
                ),
            }
        ]

        try:
            repaired_text = self._call_with_retry(
                system=repair_system,
                messages=repair_messages,
                stage=f"{stage}_repair",
                contract_name=contract_name,
                model=model,
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
        original_user_msgs: list[dict[str, str]],
        parse_result: ParseResult,
    ) -> list[dict[str, str]]:
        import json as _json

        if parse_result.raw_data:
            try:
                assistant_content = _json.dumps(parse_result.raw_data, indent=2)[:4000]
            except Exception:
                assistant_content = parse_result.raw_text[:4000]
        else:
            assistant_content = parse_result.raw_text[:4000]

        correction_user = parse_result.for_retry_prompt()
        return [
            *original_user_msgs,
            {"role": "assistant", "content": assistant_content},
            {"role": "user", "content": correction_user},
        ]
