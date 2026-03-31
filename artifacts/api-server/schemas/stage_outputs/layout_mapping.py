"""
Pydantic schema for the layout_mapping stage output.

Contract: v1/layout_architecture_mapper.json
Required fields: document_title, document_subtitle, version,
                 total_sections, print_structure, sections, navigation_map
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


class PrintStructure(BaseModel):
    model_config = ConfigDict(extra="allow")

    page_size: str = "A4"
    orientation: str = "portrait"
    columns: int = 1
    include_toc: bool = True
    include_index: bool = False


class ContentSlot(BaseModel):
    model_config = ConfigDict(extra="allow")

    slot_id: str = Field(..., min_length=1)
    slot_type: str = Field(..., min_length=1)
    source_field: str = ""
    label: str = ""
    required: bool = True


class SectionSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = ""
    reference_id: str | None = None


class LayoutSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    section_id: str = Field(..., min_length=1)
    sequence: int = Field(..., ge=0)
    title: str = Field(..., min_length=1)
    section_type: str = Field(..., min_length=1)
    page_type: str = ""
    source: SectionSource | None = None
    content_slots: list[ContentSlot] = []
    cross_references: list[str] = []


class NavigationEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    from_section: str = Field(..., min_length=1)
    to_section: str = Field(..., min_length=1)
    relationship: str = ""


class LayoutMappingOutput(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    document_title: str = Field(..., min_length=1)
    document_subtitle: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    total_sections: int = Field(..., ge=0)
    print_structure: PrintStructure
    sections: list[LayoutSection] = Field(..., min_length=1)
    navigation_map: list[NavigationEntry] = []

    @field_validator("total_sections", mode="before")
    @classmethod
    def _coerce_total(cls, v: object) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0
