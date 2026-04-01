"""Phase 2b — Senior Software Engineer: next.

Finds the next pending implement/custom decision, checks relevance,
and prints either:
    NEXT <json>   the issue to pass to the rewriter
    DONE <n>      no more issues; n = deferred (skip_for_now/skipped_re_ask) count

Usage:
    python senior_se_next_issue.py <source_path>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import anthropic

from common import decisions_path, issues_path, load_prompt, log_append, now_utc

_MODEL = "claude-opus-4-6"


class NextRunner:
    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.ip = issues_path(source_path)
        self.dp = decisions_path(source_path)
        self.issues: list[dict[str, Any]] = json.loads(self.ip.read_text(encoding="utf-8"))
        self.decisions: list[dict[str, Any]] = json.loads(self.dp.read_text(encoding="utf-8"))
        self.issues_by_id = {issue["id"]: issue for issue in self.issues}
        self.source_code = source_path.read_text(encoding="utf-8")
        self.client = anthropic.Anthropic()

    def run(self) -> None:
        actionable = [d for d in self.decisions
                      if d["action"] in ("implement", "custom") and d["status"] == "pending"]
        for decision in actionable:
            if self._process_decision(decision):
                return
        skip_count = sum(1 for d in self.decisions
                         if d["action"] in ("skip_for_now", "skipped_re_ask")
                         and d["status"] == "pending")
        print(f"DONE {skip_count}")

    def _process_decision(self, decision: dict[str, Any]) -> bool:
        """Check relevance and emit NEXT if applicable. Returns True if NEXT was emitted."""
        issue = self.issues_by_id[decision["id"]]
        self._log_relevance_check(issue)
        verdict, extra = self._check_relevance(self.source_code, issue, self.client)
        if verdict == "applicable":
            print(f"NEXT {json.dumps(issue)}")
            return True
        if verdict == "needs_update":
            return self._handle_needs_update(issue, extra)
        if verdict not in ("impossible", "no_longer_relevant"):
            # Unexpected verdict from LLM — treat as applicable
            print(f"NEXT {json.dumps(issue)}")
            return True
        self._mark_skipped(decision, issue, verdict)
        return False

    def _log_relevance_check(self, issue: dict[str, Any]) -> None:
        log_append(self.source_path, {
            "event": "relevance_check",
            "fingerprint": issue["fingerprint"],
        })

    def _handle_needs_update(self, issue: dict[str, Any], extra: str) -> bool:
        updates = self._parse_needs_update(extra)
        if not updates.get("description") or not updates.get("location"):
            # LLM didn't follow the format — treat as applicable
            print(f"NEXT {json.dumps(issue)}")
            return True
        history_entry = self._apply_issue_update(issue, updates)
        log_append(self.source_path, {
            "event": "issue_updated",
            "fingerprint": issue["fingerprint"],
            "old": history_entry,
            "new": updates,
        })
        print(f"NEXT {json.dumps(issue)}")
        return True

    def _apply_issue_update(self, issue: dict[str, Any], updates: dict[str, str]) -> dict[str, Any]:
        history_entry = {
            "description": issue["description"],
            "location": issue["location"],
            "timestamp": now_utc(),
        }
        issue.setdefault("history", []).append(history_entry)
        issue.update(updates)
        issue["last_updated"] = now_utc()
        self.ip.write_text(json.dumps(self.issues, indent=2), encoding="utf-8")
        return history_entry

    def _mark_skipped(self, decision: dict[str, Any], issue: dict[str, Any], verdict: str) -> None:
        decision["status"] = verdict
        decision["last_updated"] = now_utc()
        self.dp.write_text(json.dumps(self.decisions, indent=2), encoding="utf-8")
        log_append(self.source_path, {
            "event": "relevance_skipped",
            "fingerprint": issue["fingerprint"],
            "verdict": verdict,
        })

    @staticmethod
    def _check_relevance(source_code: str,
                         issue: dict[str, Any],
                         client: anthropic.Anthropic) -> tuple[str, str]:
        """Return (verdict, extra). verdict is one of:
          applicable         — issue still exists, fix can be applied as-is
          needs_update       — issue still exists but description/location have shifted;
                               extra contains the updated fields as a raw string
          impossible         — fix cannot be applied (location/structure gone)
          no_longer_relevant — issue already resolved by a prior fix
        """
        system_prompt = load_prompt("relevance_check_prompt.md")
        user_content = f"{source_code}\n\n---ISSUE---\n{json.dumps(issue, indent=2)}"
        response = client.messages.create(model=_MODEL,
                                          max_tokens=512,
                                          system=system_prompt,
                                          messages=[{"role": "user", "content": user_content}])
        raw = response.content[0].text.strip()
        first_line = raw.splitlines()[0].strip().lower()
        extra = "\n".join(raw.splitlines()[1:]).strip()
        return first_line, extra

    @staticmethod
    def _parse_needs_update(extra: str) -> dict[str, str]:
        """Parse 'description: ...' and 'location: ...' lines from needs_update extra."""
        result: dict[str, str] = {}
        for line in extra.splitlines():
            if line.startswith("description:"):
                result["description"] = line[len("description:"):].strip()
            elif line.startswith("location:"):
                result["location"] = line[len("location:"):].strip()
        return result


def run_next(source_path: Path) -> None:
    """Find the next pending implement/custom decision, check relevance, and print result."""
    NextRunner(source_path).run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    args = parser.parse_args()
    run_next(args.source_path)
