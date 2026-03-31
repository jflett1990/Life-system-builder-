"""
BaseModelProvider — abstract interface all model providers must implement.

Design principles:
  1. Providers know nothing about pipeline stages, contracts, or DB.
     They receive assembled prompts and return typed result objects.
  2. All three public methods are mandatory — providers cannot partially
     implement the interface.
  3. StructuredOutput and OutputValidation are immutable dataclasses so
     callers can safely cache and log them.

Adding a new provider:
  - Subclass BaseModelProvider
  - Implement all three abstract methods
  - Register the class name in config.model_provider
  - ModelService.get_provider() handles instantiation
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.contract_loader import ContractDefinition
    from core.prompt_assembler import AssembledPrompt
    from models_integration.output_validator import OutputValidation


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StructuredOutput:
    """
    Successful result from generate_structured_output.

    Attributes:
        data:             The parsed JSON dict — the authoritative output.
        raw_text:         Original model response text (for debugging/logging).
        stage:            Pipeline stage that produced this output.
        contract_name:    Name of the contract used.
        was_repaired:     True if JSON extraction required heuristic repair.
        repair_attempts:  How many repair passes were used (0 = clean parse).
        token_usage:      Optional token counts from the provider.
    """
    data: dict[str, Any]
    raw_text: str
    stage: str
    contract_name: str
    was_repaired: bool = False
    repair_attempts: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class PreviewText:
    """
    Short human-readable summary of a stage output.

    Attributes:
        text:        One-line or short paragraph of plain text.
        stage:       Stage the preview was generated for.
        from_llm:    True if an LLM call was needed; False if extracted heuristically.
    """
    text: str
    stage: str
    from_llm: bool = False

    def __str__(self) -> str:
        return self.text


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class BaseModelProvider(ABC):
    """
    Abstract base class for model providers.

    Subclasses implement three methods corresponding to the three ways
    the pipeline uses LLM capabilities:

      generate_structured_output — primary stage generation (returns JSON)
      validate_output            — structural check of a generated dict
      generate_preview_text      — lightweight summary of stage output
    """

    # ── Core generation ───────────────────────────────────────────────────────

    @abstractmethod
    def generate_structured_output(
        self,
        prompt: "AssembledPrompt",
        contract: "ContractDefinition",
    ) -> StructuredOutput:
        """
        Call the model with the assembled prompt and return a validated,
        parsed JSON dict wrapped in a StructuredOutput.

        Implementations MUST:
          - Call the provider API using the assembled messages
          - Parse the response into a dict using robust JSON extraction
          - Attempt at least one repair pass on malformed JSON before raising
          - Validate that all contract.required_output_fields are present
          - Return a StructuredOutput with was_repaired=True if repair was needed

        Raises:
          ModelProviderError    — API-level failure (rate limit, timeout, auth)
          ModelOutputError      — Could not parse response into a dict
          OutputValidationError — Response parsed but failed required fields check
        """
        ...

    @abstractmethod
    def validate_output(
        self,
        stage: str,
        output: dict[str, Any],
        required_fields: list[str],
        schema: dict[str, Any] | None = None,
    ) -> "OutputValidation":
        """
        Structurally validate a dict against contract requirements.

        This is a pure check — no model call.  Different providers may
        implement this differently (e.g. using native tool schemas, response
        format validation, etc.).

        Args:
          stage:           Pipeline stage name (for error context).
          output:          The dict to validate (typically from StructuredOutput.data).
          required_fields: List of required field names (may be dot-notated).
          schema:          Optional JSON Schema dict for type checking.

        Returns:
          OutputValidation — always (never raises).  Callers check .valid.
        """
        ...

    @abstractmethod
    def generate_preview_text(
        self,
        stage: str,
        output: dict[str, Any],
    ) -> PreviewText:
        """
        Generate a short human-readable summary of stage output.

        Implementations SHOULD:
          - Try heuristic extraction from well-known fields first (no LLM call)
          - Fall back to a lightweight LLM call only if heuristics fail
          - Never raise — return a fallback PreviewText("No preview available")
            if all strategies fail

        Args:
          stage:  Pipeline stage name.
          output: Parsed stage output dict.

        Returns:
          PreviewText — always.
        """
        ...

    # ── Optional hook ────────────────────────────────────────────────────────

    def provider_name(self) -> str:
        """Return a string identifier for this provider (used in logs)."""
        return type(self).__name__
