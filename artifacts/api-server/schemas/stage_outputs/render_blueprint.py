"""
Pydantic schema for the render_blueprint stage output.

Contract: v1/pdf_render_blueprint.json
Required fields: blueprint_name, theme, render_directives, page_count_estimate
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


class RenderDirective(BaseModel):
    """
    A single rendering instruction for one document section.
    The contract schema does not prescribe fixed fields beyond section_id,
    so extra fields are always allowed.
    """
    model_config = ConfigDict(extra="allow")

    section_id: str = Field(..., min_length=1)
    template: str = ""


class RenderBlueprintOutput(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    blueprint_name: str = Field(..., min_length=1)
    theme: dict[str, Any] = Field(..., description="Color palette, typography, spacing config")
    render_directives: list[RenderDirective] = Field(..., min_length=1)
    page_count_estimate: int = Field(..., ge=0)
    render_notes: list[str] = []

    @field_validator("theme", mode="before")
    @classmethod
    def _require_theme_dict(cls, v: object) -> dict:
        if not isinstance(v, dict):
            raise ValueError("theme must be a JSON object")
        if not v:
            raise ValueError("theme must not be empty")
        return v

    @field_validator("page_count_estimate", mode="before")
    @classmethod
    def _coerce_page_count(cls, v: object) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0
