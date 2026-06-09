from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class ProjectCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str = Field(..., max_length=200)
    # The tutorial request — what the user wants a tutorial/walkthrough on.
    topic: str = Field(..., max_length=2000)
    audience: str | None = Field(default=None, max_length=500)
    tone: str | None = Field(default=None, max_length=200)
    context: str | None = Field(default=None, max_length=5000)

    # Tutorial request controls
    skill_level: str | None = Field(default=None, max_length=50)
    tutorial_type: str | None = Field(default=None, max_length=100)
    stack: str | None = Field(default=None, max_length=500)
    platform: str | None = Field(default=None, max_length=200)
    depth: str | None = Field(default=None, max_length=50)
    include_code: bool = True
    output_style: str | None = Field(default=None, max_length=100)
    constraints: str | None = Field(default=None, max_length=2000)

    formatting_profile: str | None = Field(default=None, max_length=100)
    artifact_density: str | None = Field(default=None, max_length=100)

    @field_validator("title", "topic")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be empty")
        return v.strip()


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    title: str | None = None
    topic: str | None = None
    audience: str | None = None
    tone: str | None = None
    context: str | None = None
    skill_level: str | None = None
    tutorial_type: str | None = None
    stack: str | None = None
    platform: str | None = None
    depth: str | None = None
    include_code: bool | None = None
    output_style: str | None = None
    constraints: str | None = None
    status: str | None = None
    formatting_profile: str | None = None
    artifact_density: str | None = None


class ProjectResponse(BaseModel):
    id: int
    title: str
    topic: str
    audience: str | None
    tone: str | None
    context: str | None
    skill_level: str | None = None
    tutorial_type: str | None = None
    stack: str | None = None
    platform: str | None = None
    depth: str | None = None
    include_code: bool = True
    output_style: str | None = None
    constraints: str | None = None
    formatting_profile: str | None = None
    artifact_density: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
