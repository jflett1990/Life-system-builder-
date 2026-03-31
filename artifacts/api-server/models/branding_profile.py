"""
BrandingProfile — stub for future multi-tenant or user-defined branding.

Currently a placeholder. When activated, a project can reference a
BrandingProfile to override the default CSS token set (fonts, colours,
logo, etc.) without touching the template or contract layers.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class BrandingProfile(Base):
    __tablename__ = "branding_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    primary_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    text_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    heading_font: Mapped[str | None] = mapped_column(String(100), nullable=True)
    body_font: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    token_overrides_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def get_token_overrides(self) -> dict[str, str]:
        if self.token_overrides_json:
            return json.loads(self.token_overrides_json)
        return {}

    def set_token_overrides(self, data: dict[str, Any]) -> None:
        self.token_overrides_json = json.dumps(data, ensure_ascii=False)
