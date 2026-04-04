"""
PromptAssembler — combines contract instructions, user payload, and upstream outputs
into a final pair of OpenAI messages ready for submission.

Design:
  - system_message = orchestrator instructions + contract system instructions + mode enforcement
  - user_message   = stage header + rendered user_prompt_template + schema block + required fields

Output modes:
  - "json":          adds strict JSON-only enforcement (no markdown, no fences)
  - "markdown_json": adds instruction to return markdown prose followed by a ```json fence

The assembler is stateless. Instantiate once and call assemble() per request.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from core.logging import get_logger

if TYPE_CHECKING:
    from core.contract_loader import ContractDefinition

logger = get_logger(__name__)

_JSON_MODE_SUFFIX = (
    "\n\n--- OUTPUT MODE ---\n"
    "Return ONLY valid JSON. No markdown. No prose. No explanations. No code fences. "
    "The first character of your response must be '{' and the last must be '}'."
)

_MARKDOWN_JSON_MODE_SUFFIX = (
    "\n\n--- OUTPUT MODE ---\n"
    "Return your response in two parts:\n"
    "1. A concise narrative summary in plain prose (2-4 paragraphs).\n"
    "2. A fenced JSON block containing the full structured output:\n"
    "```json\n{ ... }\n```\n"
    "The JSON block must be complete and valid."
)

_USER_MESSAGE_HEADER = (
    "STAGE: {stage}\n"
    "CONTRACT: {contract_name} v{contract_version}\n"
    "OUTPUT MODE: {output_mode}\n"
    "{sep}\n"
)

_UPSTREAM_CONTEXT_HEADER = "\n\n--- UPSTREAM STAGE CONTEXT ---\n"

# Hard cap on how many characters of upstream JSON are included per dependency.
# Keeps total prompt tokens well within the model's context window.
# At ~4 chars/token this is ≈ 2 000 tokens per upstream stage.
_MAX_UPSTREAM_CHARS = 8000

_SCHEMA_BLOCK = (
    "\n\n--- REQUIRED OUTPUT SCHEMA ---\n"
    "{schema_json}\n"
    "\n--- REQUIRED FIELDS (must all be present and non-empty) ---\n"
    "{required_fields}\n"
)


@dataclass
class AssembledPrompt:
    stage: str | None
    contract_name: str
    contract_version: str
    output_mode: str
    system_message: str
    user_message: str

    def to_openai_messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": self.user_message},
        ]


class PromptAssemblyError(Exception):
    """Raised when the assembler cannot construct a valid prompt."""


class PromptAssembler:
    """
    Assembles final OpenAI messages from contracts + runtime data.

    Args:
        orchestrator: The life_system_orchestrator contract (always injected).
    """

    def __init__(self, orchestrator: "ContractDefinition") -> None:
        self._orchestrator = orchestrator

    def assemble(
        self,
        contract: "ContractDefinition",
        payload: dict[str, Any],
        upstream_outputs: dict[str, Any] | None = None,
        output_mode_override: str | None = None,
    ) -> AssembledPrompt:
        """
        Build an AssembledPrompt from a contract and runtime context.

        Args:
            contract:             The stage contract to use.
            payload:              Project-level fields (life_event, audience, tone, context, etc.).
            upstream_outputs:     Dict of stage_name -> parsed JSON output from upstream stages.
            output_mode_override: If set, overrides the contract's output_mode.
        """
        if not contract.has_prompt() and not contract.is_orchestrator():
            raise PromptAssemblyError(
                f"Contract '{contract.name}' has no user_prompt_template and is not an orchestrator."
            )

        output_mode = output_mode_override or contract.output_mode

        # --- Build system message ---
        system_parts: list[str] = []

        if self._orchestrator.system_instructions:
            system_parts.append(self._orchestrator.system_instructions.strip())

        if contract.system_instructions:
            system_parts.append(contract.system_instructions.strip())

        if output_mode == "json":
            system_parts.append(_JSON_MODE_SUFFIX)
        elif output_mode == "markdown_json":
            system_parts.append(_MARKDOWN_JSON_MODE_SUFFIX)
        else:
            raise PromptAssemblyError(f"Unknown output_mode: '{output_mode}'")

        system_message = "\n\n".join(system_parts)

        # --- Build user message ---
        user_parts: list[str] = []

        header = _USER_MESSAGE_HEADER.format(
            stage=contract.stage or "orchestrator",
            contract_name=contract.name,
            contract_version=contract.version,
            output_mode=output_mode,
            sep="=" * 60,
        )
        user_parts.append(header)

        # Render upstream context
        if upstream_outputs:
            upstream_block = self._render_upstream_context(
                contract.upstream_dependencies, upstream_outputs
            )
            if upstream_block:
                user_parts.append(upstream_block)

        # Render user prompt template
        if contract.user_prompt_template:
            rendered = self._render_template(
                contract.user_prompt_template,
                payload,
                upstream_outputs or {},
            )
            user_parts.append(rendered)

        # Append schema block
        if contract.output_schema:
            schema_block = _SCHEMA_BLOCK.format(
                schema_json=json.dumps(contract.output_schema, indent=2),
                required_fields="\n".join(
                    f"  - {f}" for f in contract.required_output_fields
                ),
            )
            user_parts.append(schema_block)

        user_message = "\n".join(user_parts)

        logger.debug(
            "Assembled prompt for contract '%s' v%s | mode=%s | upstream=%s",
            contract.name,
            contract.version,
            output_mode,
            list((upstream_outputs or {}).keys()),
        )

        return AssembledPrompt(
            stage=contract.stage,
            contract_name=contract.name,
            contract_version=contract.version,
            output_mode=output_mode,
            system_message=system_message,
            user_message=user_message,
        )

    def _render_upstream_context(
        self,
        dependencies: list[str],
        upstream_outputs: dict[str, Any],
    ) -> str:
        if not dependencies:
            return ""

        parts: list[str] = [_UPSTREAM_CONTEXT_HEADER.strip()]
        for dep in dependencies:
            if dep in upstream_outputs:
                label = dep.upper().replace("_", " ")
                raw = json.dumps(upstream_outputs[dep], indent=2, ensure_ascii=False)
                if len(raw) > _MAX_UPSTREAM_CHARS:
                    truncated = raw[:_MAX_UPSTREAM_CHARS]
                    # Find the last complete line to avoid cutting mid-value
                    last_nl = truncated.rfind("\n")
                    if last_nl > 0:
                        truncated = truncated[:last_nl]
                    raw = truncated + f"\n  ... [truncated — {len(raw) - len(truncated)} chars omitted]\n}}"
                    logger.warning(
                        "Upstream context for '%s' truncated to %d chars (was %d) to stay within token budget",
                        dep, _MAX_UPSTREAM_CHARS, len(json.dumps(upstream_outputs[dep], ensure_ascii=False)),
                    )
                parts.append(f"\n[{label}]\n" + raw)
            else:
                parts.append(f"\n[{dep.upper()}] — NOT YET AVAILABLE")

        return "\n".join(parts)

    def _render_template(
        self,
        template: str,
        payload: dict[str, Any],
        upstream_outputs: dict[str, Any],
    ) -> str:
        """
        Render the user_prompt_template. Supports two sets of substitution keys:
        - Top-level payload fields (life_event, audience, tone, context, ...)
        - Upstream stage outputs via key 'upstream_{stage_name}' (serialised as JSON)
        """
        context: dict[str, Any] = {
            k: v if isinstance(v, (int, float, bool)) else (str(v) if v is not None else "")
            for k, v in payload.items()
        }

        for stage_name, output in upstream_outputs.items():
            key = f"upstream_{stage_name}"
            serialised = json.dumps(output, indent=2, ensure_ascii=False)
            if len(serialised) > _MAX_UPSTREAM_CHARS:
                serialised = serialised[:_MAX_UPSTREAM_CHARS] + "\n... [truncated]"
            context[key] = serialised

        try:
            return template.format_map(_SafeDict(context))
        except Exception as exc:
            raise PromptAssemblyError(
                f"Template rendering failed for contract: {exc}"
            ) from exc


class _SafeDict(dict):
    """Returns empty string for missing keys instead of raising KeyError."""

    def __missing__(self, key: str) -> str:
        logger.warning("Prompt template missing key: '%s' — substituting empty string", key)
        return ""
