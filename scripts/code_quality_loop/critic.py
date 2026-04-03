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


class CodeCritic:
    """Evaluates source code and produces a list of quality issues."""

    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.ip = issues_path(source_path)
        self.dp = decisions_path(source_path)
        self.existing_issues: list[dict[str, Any]] = (
            json.loads(self.ip.read_text(encoding="utf-8")) if self.ip.exists() else []
        )
        self.next_id = max((issue["id"] for issue in self.existing_issues), default=0) + 1
        self.client = anthropic.Anthropic()

    def run(self) -> None:
        known_unresolved = self._known_unresolved_issues()
        user_message = self._build_user_message(known_unresolved)

        print(f"Code critic: reviewing {self.source_path.name} ...")
        new_issues = self._review(user_message)
        print(f"Code critic: found {len(new_issues)} new issue(s), "
              f"{len(known_unresolved)} already known.")

        self.ip.write_text(
            json.dumps(self.existing_issues + new_issues, indent=2), encoding="utf-8"
        )

    def _known_unresolved_issues(self) -> list[dict[str, Any]]:
        resolved_ids: set[int] = set()
        if self.dp.exists():
            decisions = json.loads(self.dp.read_text(encoding="utf-8"))
            resolved_ids = {
                d["id"] for d in decisions
                if d["status"] in ("done", "no_longer_relevant", "impossible")
            }
        return [i for i in self.existing_issues if i["id"] not in resolved_ids]

    def _build_user_message(self, known_unresolved: list[dict[str, Any]]) -> str:
        source_code = self.source_path.read_text(encoding="utf-8")
        if known_unresolved:
            return (
                f"{source_code}\n\n"
                f"---KNOWN ISSUES (do not re-report these)---\n"
                f"{json.dumps(known_unresolved, indent=2)}"
            )
        return source_code

    def _review(self, user_message: str) -> list[dict[str, Any]]:
        system_prompt = load_prompt("critic_prompt.md")
        response = self.client.messages.create(
            model=_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_issues = json.loads(strip_markdown_fence(response.content[0].text))
        return self._assign_ids(raw_issues)

    def _assign_ids(self, raw_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for ri in raw_issues:
            # Just in case the LLM happens to output a field we want to set below
            ri.pop("id", None)
            ri.pop("last_updated", None)
        now = now_utc()
        return [
            {"id": self.next_id + i, "last_updated": now, **issue}
            for i, issue in enumerate(raw_issues)
        ]


def run(source_path: Path) -> None:
    CodeCritic(source_path).run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    args = parser.parse_args()
    run(args.source_path)
