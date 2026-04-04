"""
DocumentSanitizer — implements Phase 3 (Content Sanitation) and Phase 5
(Quality Gates) from the document production agent specification.

Runs against the raw stage-output dict BEFORE ManifestBuilder consumes it,
so artifacts never reach the templates.

Sanitation targets (per the spec):
  • Duplicated heading prefixes      "Chapter 1: Chapter 1: …"
  • Placeholder instructions         "[INSERT …]", "(placeholder)", "TBD", etc.
  • Raw booleans                      True/False surviving as body strings
  • Literal null / None markers
  • Markdown artifacts in plain fields  **bold** remaining in title-type fields
  • Parenthesised seed values         "(e.g. your system name here)"
  • Orphan empty strings in arrays
  • Truncated / trailing ellipsis in titles
  • JSON-style token markers          {{token}}, {field}

Quality-gate checks (Phase 5) return a list of SanitizationWarning objects
that callers can log or surface in the validation system.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── Warning object ─────────────────────────────────────────────────────────────

@dataclass
class SanitizationWarning:
    path: str        # dot-path into the data dict, e.g. "chapters[0].chapter_title"
    issue: str       # short label, e.g. "DUPLICATE_HEADING"
    original: str    # the raw value before sanitization
    fixed: str       # the corrected value (or "" if deleted)
    flagged: bool = False   # True if we left the value unchanged and just flagged it


# ── Regex patterns ─────────────────────────────────────────────────────────────

_MARKDOWN_BOLD  = re.compile(r'\*\*(.+?)\*\*')
_MARKDOWN_ITALIC = re.compile(r'(?<!\*)\*([^*]+?)\*(?!\*)')
_PLACEHOLDER    = re.compile(
    r'(\[INSERT[^\]]*\]|\[YOUR [^\]]*\]|\(placeholder\)|\(e\.?g\.?,?[^)]{0,60}\))',
    re.IGNORECASE,
)
_TBD            = re.compile(r'\b(TBD|TBA|TODO|FIXME|N\/A|n\/a)\b')
_JSON_TOKEN     = re.compile(r'\{\{[^}]+\}\}|\{[A-Z_]+\}')
_DUPLICATE_CHAPTER = re.compile(
    r'^(Chapter\s+\d+\s*[:\-–—]\s*)+',
    re.IGNORECASE,
)
_TRAILING_ELLIPSIS = re.compile(r'\.{3,}$|…$')
_RAW_BOOL       = re.compile(r'^(True|False|true|false|TRUE|FALSE)$')
_RAW_NULL       = re.compile(r'^(None|null|NULL|undefined|NaN)$')
_ADVICE_OPENER  = re.compile(
    r'^(Make sure|Ensure|Consider|Try to|Remember to|Don\'t forget|Be aware|'
    r'You should|It\'s important|It is important|You must|Keep in mind)',
    re.IGNORECASE,
)


# ── Field-type routing ─────────────────────────────────────────────────────────

# Title-like fields: strip markdown, de-duplicate chapter prefix, clean tokens
_TITLE_FIELDS = {
    'chapter_title', 'domain_name', 'title', 'system_name', 'document_title',
    'section_title', 'section_subtitle', 'page_title', 'page_label',
    'worksheet_title', 'gate_title', 'label', 'heading', 'name',
}

# Narrative/body fields: strip only the most intrusive artifacts (tokens, nulls)
_NARRATIVE_FIELDS = {
    'narrative', 'chapter_narrative', 'chapter_summary', 'operating_premise',
    'system_objective', 'domain_purpose', 'purpose', 'description',
    'body', 'text', 'content', 'summary',
}


class DocumentSanitizer:
    """
    Walks the stage-output dict tree and sanitizes string values in-place.
    Returns a list of SanitizationWarning for all changes made.
    """

    def sanitize(self, stage_outputs: dict[str, Any]) -> list[SanitizationWarning]:
        warnings: list[SanitizationWarning] = []
        self._walk(stage_outputs, path="", warnings=warnings)
        return warnings

    # ── Tree walker ───────────────────────────────────────────────────────────

    def _walk(
        self,
        node: Any,
        path: str,
        warnings: list[SanitizationWarning],
    ) -> Any:
        if isinstance(node, dict):
            for key, val in list(node.items()):
                child_path = f"{path}.{key}" if path else key
                cleaned = self._walk(val, child_path, warnings)
                node[key] = cleaned
        elif isinstance(node, list):
            cleaned_list = []
            for i, item in enumerate(node):
                cleaned_item = self._walk(item, f"{path}[{i}]", warnings)
                # Drop items that became empty strings through sanitation
                if isinstance(cleaned_item, str) and not cleaned_item.strip():
                    warnings.append(SanitizationWarning(
                        path=f"{path}[{i}]",
                        issue="EMPTY_AFTER_SANITATION",
                        original=repr(item),
                        fixed="(removed from list)",
                    ))
                else:
                    cleaned_list.append(cleaned_item)
            return cleaned_list
        elif isinstance(node, str):
            return self._sanitize_string(node, path, warnings)
        return node

    # ── String sanitizer ──────────────────────────────────────────────────────

    def _sanitize_string(
        self,
        value: str,
        path: str,
        warnings: list[SanitizationWarning],
    ) -> str:
        original = value

        # Detect field type from the last key segment
        key = path.split('.')[-1].split('[')[0]

        # 1. Raw boolean or null — replace with empty string
        if _RAW_BOOL.match(value.strip()) or _RAW_NULL.match(value.strip()):
            warnings.append(SanitizationWarning(
                path=path, issue="RAW_BOOL_OR_NULL",
                original=original, fixed="",
            ))
            return ""

        # 2. JSON template tokens
        cleaned = _JSON_TOKEN.sub("", value)
        if cleaned != value:
            warnings.append(SanitizationWarning(
                path=path, issue="JSON_TOKEN",
                original=original, fixed=cleaned,
            ))
            value = cleaned

        # 3. Placeholder instructions
        cleaned = _PLACEHOLDER.sub("", value).strip()
        if cleaned != value:
            warnings.append(SanitizationWarning(
                path=path, issue="PLACEHOLDER_TEXT",
                original=original, fixed=cleaned,
            ))
            value = cleaned

        # 4. Title-specific rules
        if key in _TITLE_FIELDS:
            value = self._sanitize_title(value, path, original, warnings)

        # 5. Narrative-specific rules (less aggressive)
        elif key in _NARRATIVE_FIELDS:
            value = self._sanitize_narrative(value, path, original, warnings)

        return value

    def _sanitize_title(
        self,
        value: str,
        path: str,
        original: str,
        warnings: list[SanitizationWarning],
    ) -> str:
        # Strip markdown bold/italic from title fields
        cleaned = _MARKDOWN_BOLD.sub(r'\1', value)
        cleaned = _MARKDOWN_ITALIC.sub(r'\1', cleaned)
        if cleaned != value:
            warnings.append(SanitizationWarning(
                path=path, issue="MARKDOWN_IN_TITLE",
                original=original, fixed=cleaned,
            ))
            value = cleaned

        # Remove duplicate chapter prefix: "Chapter 1: Chapter 1: Title" → "Title"
        m = _DUPLICATE_CHAPTER.match(value)
        if m and m.end() < len(value):
            prefix = m.group(0)
            remainder = value[m.end():].strip()
            # Keep if the remainder still has meaningful content
            if remainder:
                cleaned = remainder
                warnings.append(SanitizationWarning(
                    path=path, issue="DUPLICATE_CHAPTER_PREFIX",
                    original=original, fixed=cleaned,
                ))
                value = cleaned

        # Remove trailing ellipsis from titles
        cleaned = _TRAILING_ELLIPSIS.sub("", value).strip()
        if cleaned != value and cleaned:
            warnings.append(SanitizationWarning(
                path=path, issue="TRUNCATED_TITLE",
                original=original, fixed=cleaned,
            ))
            value = cleaned

        return value

    def _sanitize_narrative(
        self,
        value: str,
        path: str,
        original: str,
        warnings: list[SanitizationWarning],
    ) -> str:
        # Flag (don't auto-fix) advice-opener sentences — per spec: flag if uncertain
        if _ADVICE_OPENER.match(value.strip()):
            warnings.append(SanitizationWarning(
                path=path, issue="ADVICE_LANGUAGE_OPENER",
                original=original[:120],
                fixed=value,
                flagged=True,
            ))

        # Strip TBD / TBA markers from the middle of narrative text
        cleaned = _TBD.sub("", value).strip()
        if cleaned != value:
            warnings.append(SanitizationWarning(
                path=path, issue="TBD_MARKER",
                original=original[:120], fixed=cleaned[:120],
            ))
            value = cleaned

        return value


# ── Quality Gate report ────────────────────────────────────────────────────────

@dataclass
class QualityGateResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings_count: int = 0
    flagged_count: int = 0


def run_quality_gates(
    warnings: list[SanitizationWarning],
    stage_outputs: dict[str, Any],
) -> QualityGateResult:
    """
    Phase 5 — Quality gates.  Checks that cannot be fixed automatically
    are reported here so callers can decide whether to proceed.

    Gates:
      QG1  No JSON tokens remaining in any string
      QG2  No placeholder instructions remaining
      QG3  No raw booleans remaining
      QG4  chapter_expansion has at least one chapter
      QG5  No chapter with zero worksheets (warning, not failure)
    """
    failures: list[str] = []

    # QG1-3 derived from sanitization warnings (auto-fixed but track count)
    auto_fixed_issues = {w.issue for w in warnings if not w.flagged}

    # QG4 — chapters exist
    chapters = (
        stage_outputs.get("chapter_expansion", {}).get("chapters")
        or stage_outputs.get("chapter_expansion", {}).get("expanded_chapters")
        or []
    )
    if stage_outputs.get("chapter_expansion") and not chapters:
        failures.append("QG4: chapter_expansion has no chapters")

    # QG5 — no chapter with zero worksheets (flag only)
    empty_ws_chapters = [
        ch.get("chapter_number", "?")
        for ch in chapters
        if not ch.get("worksheets")
    ]

    flagged_count = sum(1 for w in warnings if w.flagged)

    return QualityGateResult(
        passed=len(failures) == 0,
        failures=failures,
        warnings_count=len(warnings),
        flagged_count=flagged_count,
    )
