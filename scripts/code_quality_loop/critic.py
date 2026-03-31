"""Phase 1 — Critic.

Reads a Python source file, sends it to Claude for review,
assigns a sequential id to each issue, and writes the results to a JSON file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic

from common import decisions_path, issues_path, load_prompt, now_utc

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
    done_ids: set[int] = set()
    if dp.exists():
        decisions = json.loads(dp.read_text(encoding="utf-8"))
        done_ids = {d["id"] for d in decisions if d["status"] == "done"}
    known_unresolved = [i for i in existing_issues if i["id"] not in done_ids]

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

    ip.write_text(json.dumps(existing_issues + new_issues, indent=2), encoding="utf-8")
