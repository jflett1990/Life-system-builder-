"""
BrandingProfileRepository — all SQLAlchemy access for BrandingProfile.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from models.branding_profile import BrandingProfile


class BrandingProfileRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────────────

    def find_all(self) -> list[BrandingProfile]:
        return (
            self._db.query(BrandingProfile)
            .order_by(BrandingProfile.name)
            .all()
        )

    def find_by_id(self, profile_id: int) -> BrandingProfile | None:
        return (
            self._db.query(BrandingProfile)
            .filter(BrandingProfile.id == profile_id)
            .first()
        )

    def find_by_name(self, name: str) -> BrandingProfile | None:
        return (
            self._db.query(BrandingProfile)
            .filter(BrandingProfile.name == name)
            .first()
        )

    def find_default(self) -> BrandingProfile | None:
        return (
            self._db.query(BrandingProfile)
            .filter(BrandingProfile.is_default.is_(True))
            .first()
        )

    # ── Mutations ─────────────────────────────────────────────────────────────

    def insert(self, profile: BrandingProfile) -> BrandingProfile:
        self._db.add(profile)
        self._db.commit()
        self._db.refresh(profile)
        return profile

    def save(self, profile: BrandingProfile) -> BrandingProfile:
        self._db.commit()
        self._db.refresh(profile)
        return profile

    def delete(self, profile: BrandingProfile) -> None:
        self._db.delete(profile)
        self._db.commit()
