"""Phase 2a — Senior Software Engineer: triage.

Ages skip_for_now → skipped_re_ask, then classifies new issues as
implement / no / needs_human_approval.

Usage:
    python senior_se_triage.py <source_path>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import call_llm, decisions_path, issues_path, load_prompt, log_append, now_utc, \
    strip_markdown_fence

_MODEL = "claude-opus-4-6"

_TRIAGE_TO_ACTION = {
    "implement": "implement",
    "no": "no",
}


class SeniorSETriage:
    """Triages code quality issues by severity and assigns action decisions."""

    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.ip = issues_path(source_path)
        self.dp = decisions_path(source_path)
        self.issues: list[dict[str, Any]] = json.loads(self.ip.read_text(encoding="utf-8"))
        self.decisions: list[dict[str, Any]] = (
            json.loads(self.dp.read_text(encoding="utf-8")) if self.dp.exists() else []
        )

    def run(self) -> None:
        self._age_skip_decisions()
        decided_ids = {d["id"] for d in self.decisions}
        new_issues = [issue for issue in self.issues if issue["id"] not in decided_ids]
        if not new_issues:
            print("Senior SE: no new issues to triage.")
            return
        self._triage_and_record(new_issues)

    def _age_skip_decisions(self) -> None:
        aged = 0
        for d in self.decisions:
            if d["action"] == "skip_for_now":
                d["action"] = "skipped_re_ask"
                d["last_updated"] = now_utc()
                log_append(self.source_path, {
                    "event": "triage_age_skip",
                    "id": d["id"],
                    "old_action": "skip_for_now",
                    "new_action": "skipped_re_ask",
                })
                aged += 1
        if aged:
            self._save_decisions()
            print(f"Senior SE: aged {aged} skip_for_now → skipped_re_ask.")

    def _triage_and_record(self, new_issues: list[dict[str, Any]]) -> None:
        print(f"Senior SE: triaging {len(new_issues)} new issue(s) ...")
        triage_results = self._triage_issues(new_issues)
        triage_by_id = {t["id"]: t for t in triage_results}
        print("Senior SE: triage complete.")
        auto_implement, auto_no, needs_human = self._process_triage_results(
            new_issues, triage_by_id
        )
        print(f"Senior SE: {auto_implement} auto-approved, "
              f"{auto_no} auto-rejected, "
              f"{needs_human} need human review.")

    def _triage_issues(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        system_prompt = load_prompt("senior_se_triage_prompt.md")
        response_text = call_llm(
            system=system_prompt,
            user_message=json.dumps(issues, indent=2),
            max_tokens=4096,
            model=_MODEL,
        )
        return json.loads(strip_markdown_fence(response_text))

    def _process_triage_results(
            self,
            new_issues: list[dict[str, Any]],
            triage_by_id: dict[int, dict[str, Any]]) -> tuple[int, int, int]:
        auto_implement = auto_no = needs_human = 0
        for issue in new_issues:
            record = self._make_decision_record(issue, triage_by_id[issue["id"]])
            self.decisions.append(record)
            self._save_decisions()
            log_append(self.source_path, {
                "event": "triage_decision",
                "id": issue["id"],
                "fingerprint": issue["fingerprint"],
                "severity": issue["severity"],
                "action": record["action"],
                "reasoning": record["senior_se_reasoning"],
            })
            if record["action"] == "implement":
                auto_implement += 1
            elif record["action"] == "no":
                auto_no += 1
            else:
                needs_human += 1
        return auto_implement, auto_no, needs_human

    def _save_decisions(self) -> None:
        self.dp.write_text(json.dumps(self.decisions, indent=2), encoding="utf-8")

    @staticmethod
    def _make_decision_record(issue: dict[str, Any],
                              triage: dict[str, Any]) -> dict[str, Any]:
        action = _TRIAGE_TO_ACTION.get(triage["triage"], "needs_human_approval")
        return {
            "id": issue["id"],
            "action": action,
            "decision_by": "senior_se",
            "senior_se_reasoning": triage["senior_se_reasoning"],
            "status": "pending",
            "last_updated": now_utc(),
        }


def run(source_path: Path) -> None:
    ip = issues_path(source_path)
    if not ip.exists():
        print(f"Senior SE: issues file not found: {ip}")
        return
    SeniorSETriage(source_path).run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    args = parser.parse_args()
    run(args.source_path)
