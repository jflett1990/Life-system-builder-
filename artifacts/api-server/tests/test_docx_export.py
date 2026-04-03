"""
Tests for DOCX export — endpoint headers + bytes, and DocxBuilder content.

Run with:
  cd artifacts/api-server && python -m pytest tests/test_docx_export.py -v
"""
from __future__ import annotations

import io
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── DocxBuilder unit tests (no server required) ───────────────────────────────

MINIMAL_OUTPUTS: dict = {
    "system_architecture": {
        "system_name": "Test Operational System",
        "life_event": "Starting a Business",
        "system_objective": "Keep everything running smoothly.",
        "time_horizon": "6 months",
        "audience": "Founder",
    },
    "chapter_expansion": {
        "chapters": [
            {
                "chapter_number": 1,
                "chapter_title": "Foundation",
                "narrative": "This chapter covers the foundational elements.",
                "quick_reference_rules": ["Rule one.", "Rule two."],
                "worksheets": [
                    {
                        "id": "ws-form",
                        "title": "Business Identity Worksheet",
                        "purpose": "Define who you are as a business.",
                        "layout": "form",
                        "estimated_completion_time": "30 minutes",
                        "sections": [
                            {
                                "section_title": "Core Identity",
                                "instructions": "Fill in all fields.",
                                "fields": [
                                    {"label": "Business Name", "type": "text", "placeholder": "e.g. Acme Inc."},
                                    {"label": "Primary Service", "type": "text"},
                                    {
                                        "label": "Business Stage",
                                        "type": "select",
                                        "options": ["Idea", "Early", "Growth"],
                                    },
                                ],
                            }
                        ],
                        "decision_gates": [
                            {
                                "gate_id": "gate-1",
                                "condition": "Is the business name legally registered?",
                                "pass_action": "Proceed to branding.",
                                "fail_action": "Register with authorities first.",
                            }
                        ],
                    },
                    {
                        "id": "ws-checklist",
                        "title": "Launch Checklist",
                        "purpose": "Verify all launch tasks are complete.",
                        "layout": "checklist",
                        "checklist_items": [
                            "Register business name",
                            "Open business bank account",
                            "Set up accounting software",
                        ],
                        "decision_gates": [],
                    },
                    {
                        "id": "ws-table",
                        "title": "Competitor Tracker",
                        "purpose": "Track competitors and their offerings.",
                        "layout": "table",
                        "table_columns": ["Competitor", "Price Point", "Strengths", "Weaknesses"],
                        "table_row_count": 8,
                        "decision_gates": [],
                    },
                    {
                        "id": "ws-two-col",
                        "title": "Current vs Target State",
                        "purpose": "Map where you are vs where you want to be.",
                        "layout": "two-column",
                        "left_column_label": "Current State",
                        "right_column_label": "Target State",
                        "sections": [
                            {
                                "section_title": "Revenue",
                                "fields": [
                                    {"label": "Monthly Revenue", "type": "text"},
                                    {"label": "Revenue Source", "type": "text"},
                                ],
                            }
                        ],
                        "decision_gates": [],
                    },
                ],
            }
        ]
    },
}


def _build_doc(outputs: dict | None = None) -> bytes:
    from render.docx_builder import DocxBuilder

    return DocxBuilder().build(project_id=1, all_outputs=outputs or MINIMAL_OUTPUTS)


class TestDocxBuilderBytes:
    def test_returns_non_empty_bytes(self) -> None:
        result = _build_doc()
        assert isinstance(result, bytes)
        assert len(result) > 1_000, f"Expected > 1 KB, got {len(result)} bytes"

    def test_starts_with_zip_magic(self) -> None:
        result = _build_doc()
        assert result[:2] == b"PK", "DOCX must start with ZIP PK magic bytes"


class TestDocxBuilderStructure:
    """Parse the generated DOCX and assert heading hierarchy + content."""

    def _parse(self, outputs: dict | None = None):
        from docx import Document

        raw = _build_doc(outputs)
        return Document(io.BytesIO(raw))

    def test_heading_hierarchy(self) -> None:
        doc = self._parse()
        paragraphs = doc.paragraphs
        h1 = [p.text for p in paragraphs if p.style.name == "Heading 1"]
        h2 = [p.text for p in paragraphs if p.style.name == "Heading 2"]
        h3 = [p.text for p in paragraphs if p.style.name == "Heading 3"]

        assert any("Chapter 1" in t for t in h1), f"Expected chapter H1, got: {h1}"
        assert any("Business Identity Worksheet" in t for t in h2), f"H2 missing worksheet: {h2}"
        assert any("Business Name" in t for t in h3), f"H3 field label missing: {h3}"

    def test_form_layout_fill_lines(self) -> None:
        doc = self._parse()
        fill_lines = [p for p in doc.paragraphs if p.text.startswith("___")]
        assert len(fill_lines) >= 2, f"Expected fill-in lines, got {len(fill_lines)}"

    def test_form_layout_select_options(self) -> None:
        doc = self._parse()
        option_texts = [p.text for p in doc.paragraphs if "○" in p.text]
        assert len(option_texts) >= 1, "Expected radio-circle option items for 'select' field"

    def test_checklist_layout_checkboxes(self) -> None:
        doc = self._parse()
        checkbox_paras = [p for p in doc.paragraphs if "☐" in p.text]
        assert len(checkbox_paras) >= 3, f"Expected ≥3 checkbox items, got {len(checkbox_paras)}"

    def test_table_layout_word_table(self) -> None:
        doc = self._parse()
        assert len(doc.tables) >= 1, "Expected at least one Word table for 'table' layout"
        headers = [c.text for c in doc.tables[0].rows[0].cells]
        assert "Competitor" in headers, f"Expected 'Competitor' column, got: {headers}"

    def test_two_column_word_table(self) -> None:
        doc = self._parse()
        two_col_tables = [t for t in doc.tables if len(t.columns) == 3]
        assert len(two_col_tables) >= 1, "Expected a 3-column Word table for 'two-column' layout"
        headers = [c.text for c in two_col_tables[0].rows[0].cells]
        assert "Current State" in headers, f"Expected 'Current State' header, got: {headers}"
        assert "Target State" in headers, f"Expected 'Target State' header, got: {headers}"

    def test_decision_gates_present(self) -> None:
        doc = self._parse()
        gate_paras = [p for p in doc.paragraphs if "Gate:" in p.text]
        assert len(gate_paras) >= 1, "Expected decision gate paragraph"

    def test_cover_content(self) -> None:
        doc = self._parse()
        full_text = " ".join(p.text for p in doc.paragraphs)
        assert "Test Operational System" in full_text
        assert "Starting a Business" in full_text

    def test_fallback_no_chapters(self) -> None:
        outputs = {
            "system_architecture": {"system_name": "Fallback Test"},
            "worksheet_system": {
                "worksheets": [
                    {
                        "id": "ws-1",
                        "title": "Legacy Worksheet",
                        "purpose": "A worksheet from the old stage.",
                        "sections": [
                            {"section_title": "Info", "fields": [{"label": "Name", "type": "text"}]}
                        ],
                    }
                ]
            },
        }
        doc = self._parse(outputs)
        h1 = [p.text for p in doc.paragraphs if p.style.name == "Heading 1"]
        assert any("Legacy Worksheet" in t for t in h1), f"Expected legacy worksheet as H1: {h1}"
