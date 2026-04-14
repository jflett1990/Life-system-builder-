from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from render.composition_engine import compose_manual
from render.document_model import build_manual_document
from render.validation_report import validate_manual


@dataclass
class ManifestPage:
    page_id: str
    sequence: int
    archetype: str
    data: dict[str, Any]
    page_break: str = "always"


@dataclass
class RenderManifest:
    document_id: str
    document_title: str
    system_name: str
    theme_tokens: dict[str, str]
    pages: list[ManifestPage] = field(default_factory=list)
    validation_report: dict[str, Any] = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.pages)


class ManifestBuilder:
    """Build RenderManifest from a canonical manual model.

    Architecture:
      1) Content architecture layer: build_manual_document()
      2) Composition layer: compose_manual()
      3) Render validation layer: validate_manual()
    """

    def build(self, project_id: int, all_outputs: dict[str, Any], theme_tokens: dict[str, str]) -> RenderManifest:
        manual = build_manual_document(project_id, all_outputs)
        composed = compose_manual(manual)
        report = validate_manual(manual, composed)

        pages: list[ManifestPage] = []
        for idx, p in enumerate(composed.pages, start=1):
            payload = dict(p.data)
            payload["page_class"] = p.page_class
            payload["components"] = [b.component for b in p.blocks]
            pages.append(
                ManifestPage(
                    page_id=p.page_id,
                    sequence=idx,
                    archetype=p.archetype,
                    page_break=p.page_break,
                    data=payload,
                )
            )

        return RenderManifest(
            document_id=manual.id,
            document_title=manual.title,
            system_name=manual.title,
            theme_tokens=theme_tokens,
            pages=pages,
            validation_report=report.to_dict(),
        )
