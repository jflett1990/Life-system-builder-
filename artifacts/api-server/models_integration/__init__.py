"""
models_integration — provider-agnostic model integration layer.

Public exports used by the rest of the application:
  ModelService          — the only class pipeline services should import
  StructuredOutput      — return type of generate_structured_output
  PreviewText           — return type of generate_preview_text
  BaseModelProvider     — abstract base (for custom providers)
  ModelProviderError    — API-level failure
  ModelOutputError      — parse/extraction failure
  OutputValidationError — structural contract failure
  OutputValidation      — result of validate_output
"""
from models_integration.model_service import ModelService
from models_integration.base import StructuredOutput, PreviewText, BaseModelProvider
from models_integration.errors import ModelProviderError, ModelOutputError, OutputValidationError
from models_integration.output_validator import OutputValidation

__all__ = [
    "ModelService",
    "StructuredOutput",
    "PreviewText",
    "BaseModelProvider",
    "ModelProviderError",
    "ModelOutputError",
    "OutputValidationError",
    "OutputValidation",
]
