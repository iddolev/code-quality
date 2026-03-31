"""Phase 1 — Critic.

Reads a Python source file, sends it to Claude for review,
assigns a sequential id to each issue, and writes the results to a JSON file.
"""
from __future__ import annotations

import json
from pathlib import Path

import anthropic

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_MODEL = "claude-opus-4-6"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def run(source_path: Path) -> Path:
    """Run the critic on *source_path* and return the path to the issues JSON."""
    source_code = source_path.read_text(encoding="utf-8")
    system_prompt = _load_prompt("critic_prompt.md")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": source_code}],
    )
    raw_issues = json.loads(response.content[0].text)
    issues = [{"id": i + 1, **issue} for i, issue in enumerate(raw_issues)]

    issues_path = source_path.with_suffix("").with_suffix(".issues.json")
    issues_path.write_text(json.dumps(issues, indent=2), encoding="utf-8")
    return issues_path
