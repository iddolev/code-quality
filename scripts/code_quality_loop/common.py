"""Shared utilities for the code quality loop modules."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import anthropic

from dotenv import load_dotenv


load_dotenv(Path(__file__).parent.parent.parent / ".env")

ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def issues_path(source_path: Path) -> Path:
    return source_path.with_suffix("").with_suffix(".issues.json")


def decisions_path(source_path: Path) -> Path:
    return source_path.with_suffix("").with_suffix(".decisions.json")


def log_path(source_path: Path) -> Path:
    return source_path.with_suffix("").with_suffix(".log.jsonl")


def log_append(source_path: Path, entry: dict) -> None:
    """Append a JSON log entry (with timestamp injected) to the .log.jsonl file."""
    entry = {"timestamp": now_utc(), **entry}
    with log_path(source_path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def strip_markdown_fence(text: str) -> str:
    """Strip a markdown code fence if present; otherwise return the text unchanged."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n", 1)
        if len(lines) < 2:
            return text
        return lines[1].rsplit("```", 1)[0]
    return text


def load_issue_examples() -> dict[str, dict[str, list[str]]]:
    """Load issue_examples.yaml: {type_id: {severity: [example, ...]}}."""
    text = (_PROMPTS_DIR / "issue_examples.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


def format_examples_for_type(all_examples: dict[str, dict[str, list[str]]],
                             type_id: str) -> str:
    """Format examples for a single issue type as markdown."""
    type_examples = all_examples.get(type_id, {})
    if not type_examples:
        return ""
    lines = ["## Examples"]
    for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        examples = type_examples.get(severity, [])
        if examples:
            lines.append(f"\n{severity}:\n")
            for ex in examples:
                lines.append(f"- {ex}")
    return "\n".join(lines)


def load_issue_types() -> list[dict[str, str]]:
    """Parse issue_types.md into a list of {"id": ..., "body": ...} dicts."""
    text = load_prompt("issue_types.md")
    header_pattern = re.compile(r"^## (\S+)\s*$", re.MULTILINE)
    matches = list(header_pattern.finditer(text))
    result = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result.append({
            "id": match.group(1),
            "body": text[start:end].strip(),
        })
    return result


def _extract_json_object(text: str) -> str | None:
    """Find a JSON object in text by locating '{"key":' and brace-counting to the matching '}'."""
    text = text.strip()
    start_pos = text.find('{"rule":"')
    if start_pos < 0:
        start_pos = text.find('{\n"rule":')
        if start_pos < 0:
            print(
                "Warning: no JSON object starting with "
                "'{\"rule\":\"' found in response.",
                file=sys.stderr,
            )
            return None
    if text.endswith('}'):
        # Assume the JSON string goes till the end of the text
        return text[start_pos:]
    print("Warning: response does not end with '}', cannot extract JSON object.", file=sys.stderr)
    return None


_EMPTY_RESPONSES = ["{}", "{\n}", "[]", "[\n]"]


def parse_llm_response(response: str) -> dict | list[dict[str, Any]] | None:
    """Parse Claude's JSON response. Returns None if no violation found."""
    response = response.strip()
    if any(response.endswith(e) for e in _EMPTY_RESPONSES):
        return None
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        json_str = _extract_json_object(response)
        if not json_str:
            print(f"Warning: no JSON found in Claude response:\n{response[:200]}", file=sys.stderr)
            return None
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            print(f"Warning: could not parse extracted JSON:\n{json_str[:200]}", file=sys.stderr)
            return None
    return data
