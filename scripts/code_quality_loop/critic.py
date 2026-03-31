"""Phase 1 — Critic.

Reads a Python source file, sends it to Claude for review,
assigns a sequential id to each issue, and writes the results to a JSON file.

Usage:
    python critic.py <source_path>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import anthropic

from common import decisions_path, issues_path, load_prompt, now_utc, strip_markdown_fence

_MODEL = "claude-opus-4-6"


def run(source_path: Path) -> None:
    source_code = source_path.read_text(encoding="utf-8")
    system_prompt = load_prompt("critic_prompt.md")

    ip = issues_path(source_path)
    existing_issues: list[dict[str, Any]] = (
        json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else []
    )
    next_id = max((issue["id"] for issue in existing_issues), default=0) + 1

    dp = decisions_path(source_path)
    resolved_ids: set[int] = set()
    if dp.exists():
        decisions = json.loads(dp.read_text(encoding="utf-8"))
        resolved_ids = {
            d["id"] for d in decisions
            if d["status"] in ("done", "no_longer_relevant", "impossible")
        }
    known_unresolved = [i for i in existing_issues if i["id"] not in resolved_ids]

    if known_unresolved:
        user_message = (
            f"{source_code}\n\n"
            f"---KNOWN ISSUES (do not re-report these)---\n"
            f"{json.dumps(known_unresolved, indent=2)}"
        )
    else:
        user_message = source_code

    print(f"Code critic: reviewing {source_path.name} ...")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    raw_issues = json.loads(strip_markdown_fence(response.content[0].text))
    for ri in raw_issues:
        # Just in case the LLM happens to output a field we want to set below
        ri.pop("id", None)
        ri.pop("last_updated", None)
    now = now_utc()
    new_issues = [
        {"id": next_id + i, "last_updated": now, **issue}
        for i, issue in enumerate(raw_issues)
    ]
    print(f"Code critic: found {len(new_issues)} new issue(s), {len(known_unresolved)} already known.")

    ip.write_text(json.dumps(existing_issues + new_issues, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    args = parser.parse_args()
    run(args.source_path)
