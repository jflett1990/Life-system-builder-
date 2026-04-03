"""
Tests for edition theming:
  - _extract_theme_tokens injects --color-primary and backward-compat aliases
  - cover_page.html uses var(--color-primary) not var(--color-cover-bg)
  - section_divider.html uses var(--color-primary) not var(--color-divider-bg)
  - tokens.css defines --color-primary as default with aliases
  - render_blueprint prompt contains category-palette guidance table

Run with:
  cd artifacts/api-server && python -m pytest tests/test_theme_tokens.py -v
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "render", "templates", "pages")
STYLES_DIR    = os.path.join(os.path.dirname(os.path.dirname(__file__)), "render", "styles")
CONTRACT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "contracts", "v1", "pdf_render_blueprint.json")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_tokens(palette: dict | None = None, typography: dict | None = None, spacing: dict | None = None):
    from services.render_service import RenderService
    svc = RenderService.__new__(RenderService)
    all_outputs: dict = {}
    if palette is not None:
        theme: dict = {"color_palette": palette}
        if typography:
            theme["typography"] = typography
        if spacing:
            theme["spacing"] = spacing
        all_outputs = {"render_blueprint": {"theme": theme}}
    return svc._extract_theme_tokens(all_outputs)


# ── Token injection tests ─────────────────────────────────────────────────────

class TestExtractThemeTokens:
    def test_primary_sets_all_four_background_vars(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#1a3a2a"})
        assert tokens["--color-primary"]     == "#1a3a2a"
        assert tokens["--color-cover-bg"]    == "#1a3a2a"
        assert tokens["--color-divider-bg"]  == "#1a3a2a"
        assert tokens["--color-chapter-bar"] == "#1a3a2a"

    def test_accent_injected(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#1e2d40", "accent": "#c9a84c"})
        assert tokens["--color-accent"] == "#c9a84c"

    def test_caregiving_palette(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#1a3a2a", "accent": "#7aab8a"})
        assert tokens["--color-primary"] == "#1a3a2a"
        assert tokens["--color-accent"]  == "#7aab8a"

    def test_legal_palette(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#1e2d40", "accent": "#c9a84c"})
        assert tokens["--color-primary"] == "#1e2d40"
        assert tokens["--color-accent"]  == "#c9a84c"

    def test_financial_palette(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#1a2340", "accent": "#d4a017"})
        assert tokens["--color-primary"] == "#1a2340"

    def test_medical_palette(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#242424", "accent": "#4a9e8e"})
        assert tokens["--color-primary"] == "#242424"

    def test_different_life_events_produce_different_primary(self) -> None:
        caregiving = _extract_tokens(palette={"primary": "#1a3a2a"})
        legal      = _extract_tokens(palette={"primary": "#1e2d40"})
        assert caregiving["--color-primary"] != legal["--color-primary"]

    def test_missing_blueprint_returns_empty(self) -> None:
        tokens = _extract_tokens()
        assert "--color-primary"     not in tokens
        assert "--color-cover-bg"    not in tokens
        assert "--color-divider-bg"  not in tokens
        assert "--color-chapter-bar" not in tokens

    def test_missing_primary_skips_background_vars(self) -> None:
        tokens = _extract_tokens(palette={"accent": "#c9a84c"})
        assert "--color-primary"    not in tokens
        assert "--color-cover-bg"   not in tokens
        assert "--color-accent"     in tokens

    def test_typography_injected(self) -> None:
        tokens = _extract_tokens(
            palette={"primary": "#1a3a2a"},
            typography={"heading_font": "Georgia", "base_size_px": 13},
        )
        assert tokens.get("--font-heading") == "Georgia"
        assert tokens.get("--text-base") == "13px"


# ── Template file assertions ──────────────────────────────────────────────────

class TestCoverPageTemplate:
    def _read(self) -> str:
        with open(os.path.join(TEMPLATES_DIR, "cover_page.html")) as f:
            return f.read()

    def test_uses_color_primary_not_cover_bg(self) -> None:
        html = self._read()
        assert "var(--color-primary)" in html, "cover must reference --color-primary"
        assert "var(--color-cover-bg)" not in html, "cover must not hardcode old --color-cover-bg"

    def test_accent_rule_present(self) -> None:
        html = self._read()
        assert "var(--color-accent)" in html, "cover must have an accent-colored rule"


class TestSectionDividerTemplate:
    def _read(self) -> str:
        with open(os.path.join(TEMPLATES_DIR, "section_divider.html")) as f:
            return f.read()

    def test_uses_color_primary_not_divider_bg(self) -> None:
        html = self._read()
        assert "var(--color-primary)" in html, "divider must reference --color-primary"
        assert "var(--color-divider-bg)" not in html, "divider must not hardcode old --color-divider-bg"

    def test_accent_used_for_decorative_elements(self) -> None:
        html = self._read()
        # Both the section label (eyebrow) and the thin rule now use --color-accent
        assert html.count("var(--color-accent)") >= 2, "divider must use --color-accent for multiple decorative elements"


# ── tokens.css assertions ─────────────────────────────────────────────────────

class TestTokensCSS:
    def _read(self) -> str:
        with open(os.path.join(STYLES_DIR, "tokens.css")) as f:
            return f.read()

    def test_primary_defined_as_default(self) -> None:
        css = self._read()
        assert "--color-primary:" in css

    def test_cover_bg_aliases_primary(self) -> None:
        css = self._read()
        assert "--color-cover-bg:       var(--color-primary)" in css

    def test_divider_bg_aliases_primary(self) -> None:
        css = self._read()
        assert "--color-divider-bg:     var(--color-primary)" in css

    def test_chapter_bar_aliases_primary(self) -> None:
        css = self._read()
        assert "--color-chapter-bar:    var(--color-primary)" in css


# ── Blueprint prompt assertions ───────────────────────────────────────────────

class TestRenderBlueprintPrompt:
    def _prompt(self) -> str:
        with open(CONTRACT_PATH) as f:
            return json.load(f)["user_prompt_template"]

    def test_contains_palette_guidance_section(self) -> None:
        assert "COLOR PALETTE GUIDANCE" in self._prompt()

    def test_contains_all_five_categories(self) -> None:
        prompt = self._prompt()
        assert "Legal" in prompt
        assert "Caregiving" in prompt
        assert "Medical" in prompt
        assert "Financial" in prompt
        assert "Default" in prompt

    def test_contains_category_hex_values(self) -> None:
        prompt = self._prompt()
        assert "#1e2d40" in prompt   # legal deep slate
        assert "#c9a84c" in prompt   # legal gold
        assert "#1a3a2a" in prompt   # caregiving forest
        assert "#7aab8a" in prompt   # caregiving sage
        assert "#242424" in prompt   # medical charcoal
        assert "#4a9e8e" in prompt   # medical teal
        assert "#1a2340" in prompt   # financial navy
        assert "#d4a017" in prompt   # financial amber

    def test_references_life_event(self) -> None:
        assert "life_event" in self._prompt()

    def test_version_still_1_0(self) -> None:
        with open(CONTRACT_PATH) as f:
            d = json.load(f)
        assert d["version"] == "1.0", "version must stay 1.0 to match registry"
