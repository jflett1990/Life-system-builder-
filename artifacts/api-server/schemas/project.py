from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel


class ProjectCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str
    life_event: str
    audience: str | None = None
    tone: str | None = None
    context: str | None = None

    @field_validator("title", "life_event")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be empty")
        return v.strip()


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str | None = None
    life_event: str | None = None
    audience: str | None = None
    tone: str | None = None
    context: str | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: int
    title: str
    life_event: str
    audience: str | None
    tone: str | None
    context: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
