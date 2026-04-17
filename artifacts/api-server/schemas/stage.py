from datetime import datetime
from typing import Any
from pydantic import BaseModel

# v1 stages — existing pipeline (unchanged)
STAGE_NAMES = [
    "system_architecture",
    "document_outline",
    "chapter_expansion",
    "chapter_worksheets",
    "appendix_builder",
    "layout_mapping",
    "render_blueprint",
    "validation_audit",
]

# v2 stages — new pipeline additions (Phase C)
# These run as optional enhancement stages alongside the v1 pipeline.
# They enrich chapter_expansion with grounded research and voice enforcement.
V2_STAGE_NAMES = [
    "research_graph",    # Stage 1: fact retrieval + research graph build
    "content_plan",      # Stage 3: chapter depth plan + component choices
    "voice_profile",     # Stage 3b: voice constraints + banned phrase list
]

ALL_STAGE_NAMES = STAGE_NAMES + V2_STAGE_NAMES

STAGE_ORDER = {name: i for i, name in enumerate(STAGE_NAMES)}

STAGE_HYPHEN_MAP = {name: name.replace("_", "-") for name in STAGE_NAMES}
STAGE_UNDERSCORE_MAP = {v: k for k, v in STAGE_HYPHEN_MAP.items()}


def normalize_stage_name(stage: str) -> str:
    """Accept both hyphenated ('system-architecture') and underscore ('system_architecture') stage names.
    Returns the canonical underscore format used internally."""
    if stage in STAGE_NAMES:
        return stage
    if stage in STAGE_UNDERSCORE_MAP:
        return STAGE_UNDERSCORE_MAP[stage]
    return stage


class StageOutputResponse(BaseModel):
    id: int
    project_id: int
    stage: str
    status: str
    output_json: dict[str, Any] | None
    preview_text: str | None
    validation_result: dict[str, Any] | None
    error_message: str | None
    revision_number: int
    sub_progress: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": False}

    @classmethod
    def from_orm_with_json(cls, obj: Any) -> "StageOutputResponse":
        internal_name = obj.stage_name
        hyphen_name = STAGE_HYPHEN_MAP.get(internal_name, internal_name)
        return cls(
            id=obj.id,
            project_id=obj.project_id,
            stage=hyphen_name,
            status=obj.status,
            output_json=obj.get_output() if obj.json_output else {},
            preview_text=obj.preview_text,
            validation_result=obj.get_validation(),
            error_message=obj.error_message,
            revision_number=obj.revision_number,
            sub_progress=obj.get_sub_progress(),
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
