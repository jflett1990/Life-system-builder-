"""
LLMClient — thin wrapper around the OpenAI client.
All LLM calls in service modules go through this class.
Centralises retry logic, error handling, and model config.
"""
from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI, APIError, RateLimitError

from core.config import settings
from core.logging import get_logger
from core.prompt_assembler import AssembledPrompt

logger = get_logger(__name__)

_MAX_RETRIES = 3


def _build_client() -> OpenAI:
    api_key = settings.get_openai_api_key()
    base_url = settings.get_openai_base_url()
    kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": _MAX_RETRIES}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self) -> None:
        self._client = _build_client()
        self._model = settings.openai_model

    def complete(self, prompt: AssembledPrompt) -> dict[str, Any]:
        """Send assembled prompt and return parsed JSON output."""
        messages = prompt.to_openai_messages()
        logger.info(
            "LLM call | model=%s | contract=%s | mode=%s",
            self._model, prompt.contract_name, prompt.output_mode,
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                max_completion_tokens=8192,
            )
        except RateLimitError as e:
            raise LLMError(f"Rate limit exceeded: {e}") from e
        except APIError as e:
            raise LLMError(f"OpenAI API error: {e}") from e

        content = response.choices[0].message.content or ""
        logger.debug("LLM raw response length: %d chars", len(content))

        return self._extract_json(content, prompt.output_mode)

    def _extract_json(self, content: str, output_mode: str) -> dict[str, Any]:
        if output_mode == "json":
            return self._parse_strict_json(content)
        elif output_mode == "markdown_json":
            return self._extract_from_markdown(content)
        else:
            return self._parse_strict_json(content)

    def _parse_strict_json(self, content: str) -> dict[str, Any]:
        content = content.strip()
        # Strip accidental code fences
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{content[:500]}") from e

    def _extract_from_markdown(self, content: str) -> dict[str, Any]:
        fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
        if fence_match:
            try:
                return json.loads(fence_match.group(1))
            except json.JSONDecodeError:
                pass
        # Fall back to finding any JSON object
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        raise LLMError("Could not extract JSON from markdown_json response")
