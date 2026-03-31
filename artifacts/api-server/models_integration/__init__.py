"""
models_integration — provider-agnostic model integration layer.

Public exports used by the rest of the application:
  ModelService          — the only class pipeline services should import
  StructuredOutput      — return type of generate_structured_output
  PreviewText           — return type of generate_preview_text
  ParseResult           — schema validation result (raw_text, parsed_data, errors)
  BaseModelProvider     — abstract base (for custom providers)
  ModelProviderError    — API-level failure
  ModelOutputError      — parse/extraction failure
  OutputValidationError — structural contract failure (schema retry exhausted)
  OutputValidation      — result of validate_output (field presence check)
"""
from models_integration.model_service import ModelService
from models_integration.base import StructuredOutput, PreviewText, BaseModelProvider
from models_integration.errors import ModelProviderError, ModelOutputError, OutputValidationError
from models_integration.output_validator import OutputValidation
from models_integration.parser import ParseResult

__all__ = [
    "ModelService",
    "StructuredOutput",
    "PreviewText",
    "ParseResult",
    "BaseModelProvider",
    "ModelProviderError",
    "ModelOutputError",
    "OutputValidationError",
    "OutputValidation",
]
