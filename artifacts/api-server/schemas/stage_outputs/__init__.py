"""
Stage output Pydantic schemas — one per pipeline stage.

Registry maps stage_name → Pydantic model class.
Use get_schema(stage) to look up the correct class.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from pydantic import BaseModel

from schemas.stage_outputs.system_architecture import SystemArchitectureOutput
from schemas.stage_outputs.worksheet_system import WorksheetSystemOutput
from schemas.stage_outputs.layout_mapping import LayoutMappingOutput
from schemas.stage_outputs.render_blueprint import RenderBlueprintOutput
from schemas.stage_outputs.validation_audit import ValidationAuditOutput

# Maps internal stage name (underscores) → Pydantic model class
STAGE_SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "system_architecture": SystemArchitectureOutput,
    "worksheet_system":    WorksheetSystemOutput,
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
    "WorksheetSystemOutput",
    "LayoutMappingOutput",
    "RenderBlueprintOutput",
    "ValidationAuditOutput",
]
