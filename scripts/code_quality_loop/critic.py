"""Phase 1 — Critic.

Reads a Python source file, sends it to Claude for review,
assigns a sequential id to each issue, and writes the results to a JSON file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic

from common import now_utc

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_MODEL = "claude-opus-4-6"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def run(source_path: Path) -> Path:
    """Run the critic on *source_path* and return the path to the issues JSON."""
    source_code = source_path.read_text(encoding="utf-8")
    system_prompt = _load_prompt("critic_prompt.md")

    issues_path = source_path.with_suffix("").with_suffix(".issues.json")
    existing_issues: list[dict[str, Any]] = (
        json.loads(issues_path.read_text(encoding="utf-8")) if issues_path.exists() else []
    )
    next_id = max((issue["id"] for issue in existing_issues), default=0) + 1

    print(f"Code critic: reviewing {source_path.name} ...")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": source_code}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    raw_issues = json.loads(text)
    now = now_utc()
    new_issues = [
        {"id": next_id + i, "last_updated": now, **issue}
        for i, issue in enumerate(raw_issues)
    ]
    print(f"Code critic: found {len(new_issues)} new issue(s).")

    issues_path.write_text(json.dumps(existing_issues + new_issues, indent=2), encoding="utf-8")
    return issues_path
