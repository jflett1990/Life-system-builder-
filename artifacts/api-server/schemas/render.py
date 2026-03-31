from datetime import datetime
from typing import Any
from pydantic import BaseModel


class RenderResult(BaseModel):
    project_id: int
    html: str
    page_count: int


class CachedRenderInfo(BaseModel):
    project_id: int
    page_count: int
    document_title: str
    updated_at: datetime


class ExportBundle(BaseModel):
    project_id: int
    html: str
    stages_json: dict[str, Any]
    exported_at: datetime
