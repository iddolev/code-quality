"""Phase 4 — Rewriter.

Loads issues.json and decisions.json, joins by id, then applies the fix
for a single approved decision (identified by --id).

Usage:
    python rewriter.py <source_path> --id <issue_id>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import anthropic

from common import decisions_path, issues_path, load_prompt, now_utc

_MODEL = "claude-opus-4-6"
_ACTIONABLE = {"implement", "custom"}


def _effective_fix(issue: dict[str, Any], decision: dict[str, Any]) -> str:
    """Return the fix instruction: custom_fix from decision if present, else issue fix."""
    custom_fix = decision.get("custom_fix")
    return custom_fix if custom_fix is not None else issue["fix"]


def _apply_fix(
    source_code: str,
    fix_instruction: str,
    client: anthropic.Anthropic,
) -> str:
    """Apply the fix instruction and return the new file content."""
    system_prompt = load_prompt("rewriter_prompt.md")
    user_content = f"{source_code}\n\n---FIX---\n{fix_instruction}"
    response = client.messages.create(
        model=_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


def _save_decisions(decisions: list[dict[str, Any]], decisions_path: Path) -> None:
    decisions_path.write_text(json.dumps(decisions, indent=2), encoding="utf-8")


def run(source_path: Path, issue_id: int) -> None:
    """Apply the approved fix for *issue_id* to *source_path*."""
    dp = decisions_path(source_path)
    ip = issues_path(source_path)

    decisions = json.loads(dp.read_text(encoding="utf-8"))
    issues = json.loads(ip.read_text(encoding="utf-8"))
    issues_by_id = {issue["id"]: issue for issue in issues}

    decision = next(
        (d for d in decisions if d["id"] == issue_id and d["action"] in _ACTIONABLE and d["status"] == "pending"),
        None,
    )
    if decision is None:
        print(f"Rewriter: no pending actionable decision found for id {issue_id}.")
        sys.exit(1)

    issue = issues_by_id[issue_id]
    source_code = source_path.read_text(encoding="utf-8")
    fix_instruction = _effective_fix(issue, decision)
    print(f"Rewriter: applying fix for \"{issue['fingerprint']}\" ...")
    new_source = _apply_fix(source_code, fix_instruction, anthropic.Anthropic())
    source_path.write_text(new_source, encoding="utf-8")
    decision["status"] = "done"
    decision["last_updated"] = now_utc()
    _save_decisions(decisions, dp)
    print(f"Rewriter: done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    parser.add_argument("--id", dest="issue_id", type=int, required=True)
    args = parser.parse_args()
    run(args.source_path, args.issue_id)
