"""
Stage output Pydantic schemas — one per pipeline stage.

Registry maps stage_name → Pydantic model class.
Use get_schema(stage) to look up the correct class.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from pydantic import BaseModel

from schemas.stage_outputs.system_architecture import SystemArchitectureOutput
from schemas.stage_outputs.document_outline import DocumentOutlineOutput
from schemas.stage_outputs.chapter_expansion import ChapterExpansionOutput, ExpandedChapter
from schemas.stage_outputs.chapter_worksheets import ChapterWorksheetsStageOutput, ChapterWorksheetsOutput
from schemas.stage_outputs.appendix_builder import AppendixBuilderOutput
from schemas.stage_outputs.layout_mapping import LayoutMappingOutput
from schemas.stage_outputs.render_blueprint import RenderBlueprintOutput
from schemas.stage_outputs.validation_audit import ValidationAuditOutput

# Maps internal stage name (underscores) → Pydantic model class
STAGE_SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "system_architecture": SystemArchitectureOutput,
    "document_outline":    DocumentOutlineOutput,
    "chapter_expansion":   ChapterExpansionOutput,
    "chapter_worksheets":  ChapterWorksheetsStageOutput,
    "appendix_builder":    AppendixBuilderOutput,
    "layout_mapping":      LayoutMappingOutput,
    "render_blueprint":    RenderBlueprintOutput,
    "validation_audit":    ValidationAuditOutput,
}


def get_schema(stage: str) -> type[BaseModel] | None:
    """
    Return the Pydantic model class for a given stage name.
    Returns None if the stage has no registered schema.
    """
    return STAGE_SCHEMA_REGISTRY.get(stage)


__all__ = [
    "STAGE_SCHEMA_REGISTRY",
    "get_schema",
    "SystemArchitectureOutput",
    "DocumentOutlineOutput",
    "ChapterExpansionOutput",
    "ExpandedChapter",
    "ChapterWorksheetsStageOutput",
    "ChapterWorksheetsOutput",
    "AppendixBuilderOutput",
    "LayoutMappingOutput",
    "RenderBlueprintOutput",
    "ValidationAuditOutput",
]
