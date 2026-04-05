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

from common import call_llm, decisions_path, issues_path, load_prompt, log_append, now_utc, \
    strip_markdown_fence

_MODEL = "claude-opus-4-6"
_ACTIONABLE = {"implement", "custom"}
_GUIDELINES_DIR = Path(__file__).resolve().parent.parent.parent / "guidelines"


class Rewriter:
    """Rewrites source code to fix a specific issue identified by the critic."""

    def __init__(self, source_path: Path, issue_id: int):
        self.source_path = source_path
        self.issue_id = issue_id
        self.dp = decisions_path(source_path)
        self.ip = issues_path(source_path)
        self.decisions: list[dict[str, Any]] = json.loads(self.dp.read_text(encoding="utf-8"))
        issues: list[dict[str, Any]] = json.loads(self.ip.read_text(encoding="utf-8"))
        self.issues_by_id = {issue["id"]: issue for issue in issues}
        self.system_prompt = self._build_system_prompt()

    def run(self) -> None:
        decision = self._find_decision()
        if decision is None:
            print(f"Rewriter: no pending actionable decision found for id {self.issue_id}.")
            sys.exit(1)

        issue = self.issues_by_id[self.issue_id]
        fix_instruction = self._effective_fix(issue, decision)

        print(f"Rewriter: applying fix for \"{issue['fingerprint']}\" ...")
        self._apply_and_save(fix_instruction, decision)
        print("Rewriter: done.")

    def _find_decision(self) -> dict[str, Any] | None:
        return next(
            (d for d in self.decisions
             if d["id"] == self.issue_id
             and d["action"] in _ACTIONABLE
             and d["status"] == "pending"),
            None,
        )

    def _apply_and_save(self, fix_instruction: str, decision: dict[str, Any]) -> None:
        source_code = self.source_path.read_text(encoding="utf-8")
        new_source = self._apply_fix(source_code, fix_instruction)
        self.source_path.write_text(new_source, encoding="utf-8")
        decision["status"] = "to_test"
        decision["last_updated"] = now_utc()
        self.dp.write_text(json.dumps(self.decisions, indent=2), encoding="utf-8")
        issue = self.issues_by_id[self.issue_id]
        log_append(self.source_path, {
            "event": "rewrite_applied",
            "id": self.issue_id,
            "fingerprint": issue["fingerprint"],
            "fix_instruction": fix_instruction,
        })

    @staticmethod
    def _build_system_prompt() -> str:
        prompt = load_prompt("rewriter_prompt.md")
        parts = []
        for path in sorted(_GUIDELINES_DIR.glob("*_lean.md")):
            parts.append(path.read_text(encoding="utf-8"))
        if parts:
            prompt += "\n\n## Code Style Guidelines\n\n" + "\n\n".join(parts)
        return prompt

    def _apply_fix(self, source_code: str, fix_instruction: str) -> str:
        user_content = f"{source_code}\n\n---FIX---\n{fix_instruction}"
        response_text = call_llm(
            system=self.system_prompt,
            user_message=user_content,
            max_tokens=8192,
            model=_MODEL,
        )
        return strip_markdown_fence(response_text)

    @staticmethod
    def _effective_fix(issue: dict[str, Any], decision: dict[str, Any]) -> str:
        """Return the fix instruction: custom_fix from decision if present, else issue fix."""
        custom_fix = decision.get("custom_fix")
        return custom_fix if custom_fix is not None else issue["fix"]


def run(source_path: Path, issue_id: int) -> None:
    """Apply the approved fix for *issue_id* to *source_path*."""
    Rewriter(source_path, issue_id).run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    parser.add_argument("--id", dest="issue_id", type=int, required=True)
    args = parser.parse_args()
    run(args.source_path, args.issue_id)
