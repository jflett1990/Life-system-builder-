from datetime import datetime
from typing import Any
from pydantic import BaseModel

STAGE_NAMES = [
    "system_architecture",
    "worksheet_system",
    "layout_mapping",
    "render_blueprint",
    "validation_audit",
]

STAGE_ORDER = {name: i for i, name in enumerate(STAGE_NAMES)}


class StageOutputResponse(BaseModel):
    id: int
    project_id: int
    stage_name: str
    status: str
    json_output: dict[str, Any] | None
    validation_result: dict[str, Any] | None
    error_message: str | None
    revision_number: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_json(cls, obj: Any) -> "StageOutputResponse":
        return cls(
            id=obj.id,
            project_id=obj.project_id,
            stage_name=obj.stage_name,
            status=obj.status,
            json_output=obj.get_output() if obj.json_output else None,
            validation_result=obj.get_validation(),
            error_message=obj.error_message,
            revision_number=obj.revision_number,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
