"""Shared LLM-response parsing utilities (used across scripts/)."""
from __future__ import annotations

import json
import re
import sys
from typing import Any


# [\s\S]*? matches any char including newlines.
# The *? makes it non-greedy, so it matches the smallest stretch between ``` pairs
# rather than gobbling from the first ``` to the very last ``` in the text.
# Note: only handles an optional `json` language tag; other tags (e.g. ```python) are NOT stripped.
_RE_FENCE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)```")
_RE_JSON_OBJ_START = re.compile(r'\{\s*"(?:rule|fingerprint)":')
_RE_JSON_ARRAY_START = re.compile(r'\[\s*\{\s*"(?:rule|fingerprint)":')


def _extract_json(text: str) -> str | None:
    """Extract JSON from *text* that may contain prose and/or markdown fences.

    The real answer is always at the END (Claude may output a possibly fenced block, then
    correct itself and output something else afterwards).  Strategy:
      1. Unwrap all markdown fences: replace ```(json)?...``` with their content.
      2. Strip and search backwards from the end for a JSON start: ``[{``, ``[\\n{``,
         ``{``, or ``{\\n`` — then take from that start to the end of the string.

    Returns the raw JSON substring, or None if no JSON structure was found.
    """
    # 1. Unwrap all fenced blocks, keeping only their content.
    unwrapped = _RE_FENCE.sub(r"\1", text).strip()

    # 2. Check for empty containers at the very end (e.g. "...corrected.\n[]")
    if unwrapped.endswith("[]") or unwrapped.endswith("{}"):
        return unwrapped[-2:]

    # 3. Must end with } or ] — otherwise there's no JSON at the end.
    if unwrapped.endswith("}"):
        pattern = _RE_JSON_OBJ_START
    elif unwrapped.endswith("]"):
        pattern = _RE_JSON_ARRAY_START
    else:
        return None

    # Find the last occurrence (the real answer, not earlier prose).
    matches = list(pattern.finditer(unwrapped))
    return unwrapped[matches[-1].start():] if matches else None


def parse_llm_response(response: str, *, label: str = "") -> list[dict[str, Any]] | None:
    """Parse Claude's JSON response.

    Returns the parsed list[dict], or None on parse failure.
    If the parsed result is a single dict, it is wrapped in a list so callers
    always receive list[dict] | None.  Empty containers ({} or [])
    are returned as-is — callers decide what empty means.
    """
    prefix = f"[{label}] " if label else ""
    json_str = _extract_json(response)
    if not json_str:
        print(f"Warning: {prefix}no JSON found in Claude response:\n"
              f"{response[:200]}", file=sys.stderr)
        return None
    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            return [parsed]
        return parsed
    except json.JSONDecodeError:
        print(f"Warning: {prefix}could not parse extracted JSON:\n{json_str[:200]}",
              file=sys.stderr)
        return None
