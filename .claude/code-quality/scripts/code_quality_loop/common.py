"""Shared utilities for the code quality loop modules."""
from __future__ import annotations

import functools
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(filename: str) -> str:
    """Read and return the contents of *filename* from the prompts/ directory (UTF-8)."""
    path = _PROMPTS_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Prompt file '{filename}' not found in {_PROMPTS_DIR}") from e


def issues_path(source_path: Path) -> Path:
    """Return the .issues.json sidecar path for *source_path*."""
    return source_path.parent / (source_path.stem + ".issues.json")


def decisions_path(source_path: Path) -> Path:
    """Return the .decisions.json sidecar path for *source_path*."""
    return source_path.parent / (source_path.stem + ".decisions.json")


def log_path(source_path: Path) -> Path:
    """Return the .log.jsonl sidecar path for *source_path*."""
    return source_path.parent / (source_path.stem + ".log.jsonl")


def log_append(source_path: Path, entry: dict) -> None:
    """Append a JSON log entry (with timestamp injected) to the .log.jsonl file."""
    entry = {"timestamp": now_utc(), **entry}
    try:
        with log_path(source_path).open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"Warning: failed to write log entry: {e}", file=sys.stderr)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def strip_markdown_fence(text: str) -> str:
    """Strip a markdown code fence if present; otherwise return the text unchanged."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n", 1)
        if len(lines) < 2:
            return ""
        return lines[1].rsplit("```", 1)[0]
    return text


@functools.lru_cache(maxsize=1)
def load_issue_examples() -> dict[str, dict[str, list[str]]]:
    """Load issue_examples.yaml: {type_id: {severity: [example, ...]}}."""
    text = (_PROMPTS_DIR / "issue_examples.yaml").read_text(encoding="utf-8")
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        print(f"Warning: failed to parse issue_examples.yaml: {e}", file=sys.stderr)
        return {}


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


_RE_ISSUE_HEADER = re.compile(r"^## (\S+)\s*$", re.MULTILINE)


def load_issue_types() -> list[dict[str, str]]:
    """Parse issue_types.md into a list of {"id": ..., "body": ...} dicts."""
    text = load_prompt("issue_types.md")
    matches = list(_RE_ISSUE_HEADER.finditer(text))
    result = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result.append({
            "id": match.group(1),
            "body": text[start:end].strip(),
        })
    return result
