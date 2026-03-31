"""
JSON extraction and repair utilities.

Handles every format a language model might return JSON in:
  - Pure JSON (ideal)
  - JSON inside a markdown code fence (```json ... ```)
  - JSON embedded in prose with surrounding text
  - Truncated JSON (last-resort repair via re-serialisation)

Strategy for invalid output:
  1. Strip fences / leading prose
  2. Try strict json.loads
  3. Try largest {...} block found by regex
  4. Try heuristic brace-balancing repair
  5. Raise ModelOutputError with full context

All functions are pure — no I/O, no LLM calls.
"""
from __future__ import annotations

import json
import re
from typing import Any

from models_integration.errors import ModelOutputError


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_json(
    text: str,
    *,
    output_mode: str = "json",
    stage: str | None = None,
    contract_name: str | None = None,
) -> dict[str, Any]:
    """
    Extract a JSON object from model output text.

    Args:
        text:          Raw model response text.
        output_mode:   "json" or "markdown_json".
        stage:         Pipeline stage name (for error context).
        contract_name: Contract name (for error context).

    Returns:
        Parsed dict.

    Raises:
        ModelOutputError if no valid JSON object can be extracted.
    """
    if not text or not text.strip():
        raise ModelOutputError(
            "Model returned empty response",
            stage=stage,
            contract_name=contract_name,
            raw_text=text or "",
        )

    cleaned = _strip_fences(text)

    # Strategy 1 — parse as-is
    result = _try_parse(cleaned)
    if result is not None:
        return result

    # Strategy 2 — markdown: look for ```json ... ``` block
    if output_mode == "markdown_json":
        result = _extract_fenced_block(text)
        if result is not None:
            return result

    # Strategy 3 — largest {...} blob via regex
    result = _extract_largest_object(text)
    if result is not None:
        return result

    # Strategy 4 — heuristic brace balancing
    result = _brace_balance_repair(text)
    if result is not None:
        return result

    raise ModelOutputError(
        "Could not extract valid JSON from model response",
        stage=stage,
        contract_name=contract_name,
        raw_text=text,
        parse_error="all extraction strategies failed",
    )


def repair_json(
    text: str,
    *,
    stage: str | None = None,
    contract_name: str | None = None,
) -> dict[str, Any] | None:
    """
    Attempt aggressive repair of a known-bad JSON string.
    Returns None if repair is impossible (caller should raise).

    Used as the second-pass repair when extract_json fails and the
    service wants to give the response a final chance.
    """
    for strategy in (_strip_fences, _identity):
        cleaned = strategy(text)
        result = _try_parse(cleaned)
        if result is not None:
            return result
        result = _extract_largest_object(cleaned)
        if result is not None:
            return result
        result = _brace_balance_repair(cleaned)
        if result is not None:
            return result
    return None


# ---------------------------------------------------------------------------
# Internal strategies
# ---------------------------------------------------------------------------

def _identity(text: str) -> str:
    return text


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from start/end."""
    text = text.strip()
    # Remove opening fence (```json or ```)
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _try_parse(text: str) -> dict[str, Any] | None:
    """Attempt json.loads; return None on any failure."""
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _extract_fenced_block(text: str) -> dict[str, Any] | None:
    """Find and parse a ```json ... ``` block."""
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result = _try_parse(match.group(1))
            if result is not None:
                return result
    return None


def _extract_largest_object(text: str) -> dict[str, Any] | None:
    """
    Find all {...} blobs in the text, sorted by descending length,
    and try to parse each one.
    """
    candidates = re.findall(r"\{[\s\S]*?\}", text)
    # Also try the greedy version (for nested objects)
    greedy = re.search(r"\{[\s\S]*\}", text)
    if greedy:
        candidates.insert(0, greedy.group(0))

    seen: set[int] = set()
    for candidate in candidates:
        h = hash(candidate)
        if h in seen:
            continue
        seen.add(h)
        result = _try_parse(candidate)
        if result is not None:
            return result
    return None


def _brace_balance_repair(text: str) -> dict[str, Any] | None:
    """
    Find the first '{', scan for balanced close.
    If the JSON is truncated, add closing brackets/braces in reverse stack order.
    Handles both { } and [ ] nesting.
    """
    start = text.find("{")
    if start == -1:
        return None

    stack: list[str] = []
    in_string = False
    escape_next = False
    _CLOSE = {"{": "}", "[": "]"}
    _OPEN = {"}": "{", "]": "["}

    for i, ch in enumerate(text[start:], start=start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append(ch)
        elif ch in ("}", "]"):
            if stack and stack[-1] == _OPEN.get(ch):
                stack.pop()
                if not stack:
                    # Balanced — try a clean parse from start to here
                    candidate = text[start : i + 1]
                    result = _try_parse(candidate)
                    if result is not None:
                        return result
                    # Balanced but still invalid (e.g. trailing comma) — stop scanning
                    break

    # Truncated — close unclosed brackets/braces in reverse order
    if stack and len(stack) <= 20:
        closes = "".join(_CLOSE[opener] for opener in reversed(stack))
        candidate = text[start:].rstrip().rstrip(",")
        # If we're inside an unclosed string, close it first
        if in_string:
            candidate += '"'
        repaired = candidate + closes
        result = _try_parse(repaired)
        if result is not None:
            return result
        # Also try dropping the last partial token before closing
        if in_string:
            # Find the last unmatched quote and truncate before it
            last_quote = candidate.rfind('"')
            if last_quote != -1:
                truncated = candidate[:last_quote].rstrip().rstrip(",").rstrip(":").rstrip()
                result = _try_parse(truncated + closes)
                if result is not None:
                    return result

    # Last resort: truncate at the last comma (drop partial trailing field)
    last_comma = text.rfind(",")
    if last_comma != -1:
        after_comma = text[last_comma + 1:].strip()
        # Only drop if what follows the comma looks partial (contains no valid value)
        if not re.search(r':\s*[\[{"\d\-tfn]', after_comma):
            candidate = text[start : last_comma].rstrip() + "}"
            # Add closing brackets for any still-open arrays
            open_brackets = candidate.count("[") - candidate.count("]")
            if 0 < open_brackets <= 10:
                candidate = candidate[:-1] + "]" * open_brackets + "}"
            result = _try_parse(candidate)
            if result is not None:
                return result

    return None


# ---------------------------------------------------------------------------
# Utility: detect whether text looks like it contains JSON
# ---------------------------------------------------------------------------

def looks_like_json(text: str) -> bool:
    """Quick heuristic: does this text contain something that might be JSON?"""
    stripped = text.strip()
    return stripped.startswith("{") or "```json" in stripped.lower() or "```" in stripped
