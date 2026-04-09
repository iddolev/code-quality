"""Phase 1 — Critic.

Reads a Python source file, sends it to Claude for review,
assigns a sequential id to each issue, and writes the results to a JSON file.

Usage:
    python critic.py <source_path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from call_llm import call_llm
from code_quality_loop.common import decisions_path, format_examples_for_type, \
    issues_path, load_issue_examples, load_issue_types, load_prompt, log_append, \
    now_utc
from common import parse_llm_response
from parent_context import gather_external_context

_MODEL = "claude-opus-4-6"


class CodeCritic:
    """Evaluates source code and produces a list of quality issues."""

    def __init__(self, source_path: Path):
        self.source_path = source_path.resolve()
        self.ip = issues_path(source_path)
        self.dp = decisions_path(source_path)
        self.existing_issues: list[dict[str, Any]] = (
            json.loads(self.ip.read_text(encoding="utf-8")) if self.ip.exists() else []
        )
        self.next_id = max((issue["id"] for issue in self.existing_issues), default=0) + 1
        self.issue_types = load_issue_types()
        self.issue_examples = load_issue_examples()
        self.external_ctx = gather_external_context(source_path)
        self.source_code = source_path.read_text(encoding="utf-8")
        self.all_types_text = "\n\n".join(t["body"] for t in self.issue_types)
        self.non_other = [t for t in self.issue_types if t["id"] != "other"]
        self.prompt_template = load_prompt("critic_prompt.md")
        self.known_unresolved = self._known_unresolved_issues()
        self.message_for_llm = self._build_message_for_llm(self.known_unresolved)

    def run(self) -> None:
        print(f"Code critic: reviewing {self.source_path} ...")
        new_issues = self._review()
        print(f"Code critic: found {len(new_issues)} new issue(s), "
              f"{len(self.known_unresolved)} already known.")

        log_append(self.source_path, {
            "event": "critic_complete",
            "new_issues": [
                {"id": issue["id"], "fingerprint": issue["fingerprint"],
                 "severity": issue["severity"], "location": issue["location"]}
                for issue in new_issues
            ],
            "known_unresolved_count": len(self.known_unresolved),
        })

        self.ip.write_text(
            json.dumps(self.existing_issues + new_issues, indent=2), encoding="utf-8"
        )

    def _known_unresolved_issues(self) -> list[dict[str, Any]]:
        resolved_ids: set[int] = set()
        if self.dp.exists():
            decisions = json.loads(self.dp.read_text(encoding="utf-8"))
            resolved_ids = {
                d["id"] for d in decisions
                if d["status"] in ("done", "to_test", "no_longer_relevant", "impossible")
            }
        return [issue for issue in self.existing_issues if issue["id"] not in resolved_ids]

    def _build_message_for_llm(self, known_unresolved: list[dict[str, Any]]) -> str:
        parts = [self.external_ctx, self.source_code] if self.external_ctx else [self.source_code]
        if known_unresolved:
            parts.append(
                "---KNOWN ISSUES (do not re-report these)---\n"
                f"{json.dumps(known_unresolved, indent=2)}"
            )
        return "\n\n".join(parts)

    _FOCUS_PREFIX = "In this round, you should focus only on issues that can be categorised as:"

    def _review(self) -> list[dict[str, Any]]:
        all_raw: list[dict[str, Any]] = []

        for issue_type in self.non_other:
            rule_title, rule_body = issue_type["body"][3:].split("\n", 1)
            rule_body = rule_body.strip()
            # Remove initial upper unless it's an uppercase acronym
            # "Ul..." -> "ul..."  but  "API..." -> keep
            if not rule_body[:2].isupper():
                rule_body = rule_body[0].lower() + rule_body[1:]
            rule_section = f"## Focus Rule: {rule_title}\n\n{self._FOCUS_PREFIX} {rule_body}"
            examples = format_examples_for_type(self.issue_examples, issue_type["id"])
            system_prompt = (
                self.prompt_template
                .replace("{{RULE_SECTION}}", rule_section)
                .replace("{{EXAMPLES}}", examples)
            )
            all_raw.extend(
                self._run_on_type(system_prompt, issue_type["id"]))

        # "other" run: all types visible, find only uncategorised issues
        rule_section = (
            f"## Issue types\n\n{self.all_types_text}\n\n"
            "Report ONLY issues that do NOT fit any of the types listed above. "
            "Use type 'other' for these. "
            "If every issue already fits an existing type, return []."
        )
        examples = format_examples_for_type(self.issue_examples, "other")
        system_prompt = (
            self.prompt_template
            .replace("{{RULE_SECTION}}", rule_section)
            .replace("{{EXAMPLES}}", examples)
        )
        all_raw.extend(self._run_on_type(system_prompt, "other"))

        return self._assign_ids(all_raw)

    def _run_on_type(self, system_prompt: str,
                     type_id: str) -> list[dict[str, Any]]:
        raw = self._call_critic(system_prompt, self.message_for_llm)
        # Add type as the first field in each issue dict
        ret = [{'type': type_id, **issue}
               for issue in raw]
        print(f"  {type_id}: {len(ret)} issue(s)")
        return ret

    @staticmethod
    def _call_critic(system_prompt: str, message_for_llm: str) -> list[dict[str, Any]]:
        response_text = call_llm(
            system_message=system_prompt,
            user_message=message_for_llm,
            max_tokens=4096,
            model=_MODEL,
        )
        return parse_llm_response(response_text) or []

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
