"""Shared utilities for the code quality loop modules."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

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
