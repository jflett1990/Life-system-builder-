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

    def test_web_frontend_palette(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#1e1b4b", "accent": "#8b9cf9"})
        assert tokens["--color-primary"] == "#1e1b4b"
        assert tokens["--color-accent"]  == "#8b9cf9"

    def test_backend_palette(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#0f3a3d", "accent": "#5fb3a1"})
        assert tokens["--color-primary"] == "#0f3a3d"
        assert tokens["--color-accent"]  == "#5fb3a1"

    def test_devops_palette(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#1e2d40", "accent": "#c9a84c"})
        assert tokens["--color-primary"] == "#1e2d40"

    def test_ai_ml_palette(self) -> None:
        tokens = _extract_tokens(palette={"primary": "#2a1b40", "accent": "#b48ead"})
        assert tokens["--color-primary"] == "#2a1b40"

    def test_different_topics_produce_different_primary(self) -> None:
        web    = _extract_tokens(palette={"primary": "#1e1b4b"})
        devops = _extract_tokens(palette={"primary": "#1e2d40"})
        assert web["--color-primary"] != devops["--color-primary"]

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

    def _read_base_css(self) -> str:
        with open(os.path.join(STYLES_DIR, "base.css")) as f:
            return f.read()

    def test_cover_background_uses_color_primary(self) -> None:
        # The cover background lives on .page--cover_page in base.css,
        # not inside the template itself.
        css = self._read_base_css()
        assert ".page--cover_page" in css
        assert "var(--color-primary)" in css, "cover background must reference --color-primary"
        assert "var(--color-cover-bg)" not in self._read(), "cover must not hardcode old --color-cover-bg"

    def test_accent_rule_present(self) -> None:
        html = self._read()
        assert "var(--color-accent)" in html, "cover must have an accent-colored rule"


class TestSectionDividerTemplate:
    def _read(self) -> str:
        with open(os.path.join(TEMPLATES_DIR, "section_divider.html")) as f:
            return f.read()

    def _read_base_css(self) -> str:
        with open(os.path.join(STYLES_DIR, "base.css")) as f:
            return f.read()

    def test_divider_background_uses_color_primary(self) -> None:
        # The divider background lives on .page--section_divider in base.css,
        # not inside the template itself.
        css = self._read_base_css()
        assert ".page--section_divider" in css
        assert "var(--color-primary)" in css, "divider background must reference --color-primary"
        assert "var(--color-divider-bg)" not in self._read(), "divider must not hardcode old --color-divider-bg"

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
        assert "Web / frontend" in prompt
        assert "Backend" in prompt
        assert "DevOps" in prompt
        assert "AI / ML" in prompt
        assert "Default" in prompt

    def test_contains_category_hex_values(self) -> None:
        prompt = self._prompt()
        assert "#1e1b4b" in prompt   # web deep indigo
        assert "#8b9cf9" in prompt   # web periwinkle
        assert "#0f3a3d" in prompt   # backend deep teal
        assert "#5fb3a1" in prompt   # backend seafoam
        assert "#1e2d40" in prompt   # devops deep slate
        assert "#c9a84c" in prompt   # devops gold
        assert "#2a1b40" in prompt   # ai deep violet
        assert "#b48ead" in prompt   # ai orchid

    def test_references_topic(self) -> None:
        assert "topic" in self._prompt()

    def test_version_still_1_0(self) -> None:
        with open(CONTRACT_PATH) as f:
            d = json.load(f)
        assert d["version"] == "1.0", "version must stay 1.0 to match registry"
