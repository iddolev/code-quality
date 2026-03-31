"""Phase 3 — Rewriter.

Loads issues.json and decisions.json, joins by id, then for each approved
decision checks relevance and applies the fix to the source file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_MODEL = "claude-opus-4-6"
_ACTIONABLE = {"implement", "custom"}


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _effective_fix(issue: dict[str, Any], decision: dict[str, Any]) -> str:
    """Return the fix instruction: custom_fix from decision if present, else issue fix."""
    return decision.get("custom_fix") or issue["fix"]


def _check_relevance(
    source_code: str,
    issue: dict[str, Any],
    client: anthropic.Anthropic,
) -> tuple[str, str]:
    """Return (verdict, explanation). verdict is one of: applicable, impossible, no_longer_relevant."""
    system_prompt = _load_prompt("relevance_check_prompt.md")
    user_content = f"{source_code}\n\n---ISSUE---\n{json.dumps(issue, indent=2)}"
    response = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = response.content[0].text.strip()
    first_line = raw.splitlines()[0].strip()
    explanation = "\n".join(raw.splitlines()[1:]).strip()
    return first_line, explanation


def _apply_fix(
    source_code: str,
    fix_instruction: str,
    client: anthropic.Anthropic,
) -> str:
    """Apply the fix instruction and return the new file content."""
    system_prompt = _load_prompt("rewriter_prompt.md")
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


def run(source_path: Path, decisions_path: Path) -> None:
    """Apply all approved fixes from *decisions_path* to *source_path*."""
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))

    issues_path = decisions_path.with_name(
        decisions_path.name.replace(".decisions.json", ".issues.json")
    )
    issues = json.loads(issues_path.read_text(encoding="utf-8"))
    issues_by_id = {issue["id"]: issue for issue in issues}

    client = anthropic.Anthropic()

    actionable = [d for d in decisions if d["action"] in _ACTIONABLE]
    total = len(actionable)
    applied = 0

    for decision in actionable:
        issue = issues_by_id[decision["id"]]
        source_code = source_path.read_text(encoding="utf-8")
        verdict, explanation = _check_relevance(source_code, issue, client)

        if verdict in ("impossible", "no_longer_relevant"):
            decision["status"] = verdict
            decision["explanation"] = explanation
            _save_decisions(decisions, decisions_path)
            print(f"Skipped ({verdict}): {issue['fingerprint']}")
            continue

        fix_instruction = _effective_fix(issue, decision)
        new_source = _apply_fix(source_code, fix_instruction, client)
        source_path.write_text(new_source, encoding="utf-8")
        decision["status"] = "done"
        _save_decisions(decisions, decisions_path)
        applied += 1
        print(f"Applied fix {applied}/{total}: {issue['fingerprint']}")
