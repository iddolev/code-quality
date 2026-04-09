"""Apply visual flow guidelines to a source code file using Claude.

For each rule in the guidelines file, sends the code to Claude with the
corresponding prompt and scope, then applies the returned patch.

Usage:
    python .claude/code-quality/scripts/visual_flow/visual_flow_applier.py \
        <guidelines_file> <source_file>

Example:
    python .claude/code-quality/scripts/visual_flow/visual_flow_applier.py \
        .claude/code-quality/guidelines/visual_flow.md src/app.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile

from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from call_llm import call_llm
from parse_llm_response import parse_llm_response

load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPT_TEMPLATE_PATH = SCRIPT_DIR / "visual_flow_prompt.md"
_PROMPT_TEMPLATE = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
_CONFIG = {
    "model": "claude-sonnet-4-6",
    "repetitions": 1,
}

VALID_SCOPES = {"local", "medium", "file"}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".kt", ".go", ".rs", ".rb",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".swift", ".scala", ".sh", ".bash",
}


def parse_rules(guidelines_path: Path) -> list[dict]:
    """Parse the guidelines file into a list of rules.

    Each rule has: id (str), title (str), scope (str), body (str).
    """
    text = guidelines_path.read_text(encoding="utf-8")
    rule_pattern = re.compile(
        r"^## (\d+)\. (.+)$",
        re.MULTILINE,
    )
    matches = list(rule_pattern.finditer(text))
    rules = []
    for i, match in enumerate(matches):
        rule_id = int(match.group(1))
        title = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        body = re.sub(r'<a\s+id="[^"]*"\s*/?\s*>\s*', "", body).rstrip()

        scope_match = re.search(r"\n>\s*scope:\s*(\w+)\n", body)
        if not scope_match:
            print(f"Warning: rule {rule_id} has no scope, skipping.", file=sys.stderr)
            continue
        body = body[:scope_match.start()] + body[scope_match.end():]
        body = body.strip()
        scope = scope_match.group(1).strip().lower()
        if scope not in VALID_SCOPES:
            print(
                f"Warning: rule {rule_id} has unknown scope '{scope}', skipping.",
                file=sys.stderr,
            )
            continue

        rules.append({
            "id": rule_id,
            "title": title,
            "scope": scope,
            "body": body,
        })
    return rules


def build_prompt(rule: dict, code: str) -> str:
    """Build the full prompt for Claude by combining template, scope section, rule, and code."""

    prompt_template = _PROMPT_TEMPLATE.replace("#<N>", f"#<{rule['id']}>")
    return (
        f"{prompt_template}\n\n"
        "---\n\n"
        f"## Rule {rule['body'][3:]}\n\n"
        "---\n\n"
        f"## Code:\n\n```\n{code}\n```"
    )


_SYSTEM_PROMPT = (
    "You are a code review tool. Your output is consumed by a machine parser. "
    "You must respond with ONLY a valid JSON object, no prose, no markdown fences, no extra text."
)


def call_claude(prompt: str) -> str:
    """Send the prompt to Claude and return the response text."""
    return call_llm(
        system_message=_SYSTEM_PROMPT,
        user_message=prompt,
        model=_CONFIG["model"],
    )


_APPROVAL_SYSTEM_PROMPT ="""
You are an elite software engineer, an expert in determining 
whether a code rewrite preserves semantics (i.e. same output for same input).
"""

_APPROVAL_PROMPT ="""
Below is a unified diff format ("patch file") for a change to code. 
Read it and determine: does the change preserve semantics (i.e. same output for same input)? 
Answer with only YES or NO.
"""


def _approve_change(diff_text: str) -> bool:
    """Ask Claude whether the diff preserves semantics. Returns True if approved."""
    content = f"{_APPROVAL_PROMPT.strip()}\n\n```\n{diff_text}\n```"
    response_text = call_llm(
        system_message=_APPROVAL_SYSTEM_PROMPT.strip(),
        user_message=content,
        max_tokens=16,
        model=_CONFIG["model"],
    )
    answer = response_text.strip().upper()
    return answer.startswith("YES")


def _fix_hunk_headers(diff_text: str) -> str:
    """Recalculate hunk headers in a unified diff, since LLMs often get the line counts wrong."""
    lines = diff_text.splitlines(keepends=True)
    result = []
    hunk_start = None
    old_count = 0
    new_count = 0

    for _i, line in enumerate(lines):
        if line.startswith("@@"):
            if hunk_start is not None:
                result[hunk_start] = _build_hunk_header(result[hunk_start], old_count, new_count)
            hunk_start = len(result)
            old_count = 0
            new_count = 0
            result.append(line)
        elif hunk_start is None:
            result.append(line)
        elif line.startswith("-"):
            old_count += 1
            result.append(line)
        elif line.startswith("+"):
            new_count += 1
            result.append(line)
        else:
            # context line (starts with space or is empty)
            old_count += 1
            new_count += 1
            result.append(line)

    if hunk_start is not None:
        result[hunk_start] = _build_hunk_header(result[hunk_start], old_count, new_count)

    return "".join(result)


def _build_hunk_header(original_header: str, old_count: int, new_count: int) -> str:
    """Replace the line counts in a @@ header while preserving the start line numbers."""
    match = re.match(r"@@ -(\d+),?\d* \+(\d+),?\d* @@(.*)", original_header)
    if not match:
        return original_header
    old_start = match.group(1)
    new_start = match.group(2)
    trailing = match.group(3)
    return f"@@ -{old_start},{old_count} +{new_start},{new_count} @@{trailing}\n"


def apply_patch(original_code: str, diff_text: str, source_path: Path) -> str | None:
    """Apply a unified diff patch to the original code. Returns patched code or None on failure."""
    diff_text = _fix_hunk_headers(diff_text)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        original_file = tmpdir_path / source_path.name
        original_file.write_text(original_code, encoding="utf-8")

        patch_file = tmpdir_path / "change.patch"
        patch_file.write_text(diff_text, encoding="utf-8")

        result = subprocess.run(
            ["patch", "--no-backup-if-mismatch", "-p1", str(original_file)],
            input=diff_text,
            capture_output=True,
            text=True,
            cwd=tmpdir,
            check=False,
        )
        if result.returncode != 0:
            print(f"Warning: patch failed:\n{result.stderr}\n{result.stdout}", file=sys.stderr)
            return None

        return original_file.read_text(encoding="utf-8")


def log_fix(log_path: Path, rule: dict, response_data: dict) -> None:
    """Append a JSONL entry for the applied fix."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "rule": response_data.get("rule", f"visual flow #{rule['id']}"),
        "location": response_data.get("location", ""),
        "description": response_data.get("description", ""),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def compute_log_path(source_path: Path) -> Path:
    """Compute the log file path: /tmp/<relative_filepath>.vf.jsonl."""
    try:
        relative = source_path.resolve().relative_to(Path.cwd())
    except ValueError:
        relative = source_path
    return Path("/temp") / f"{relative}.vf.jsonl"


def _apply_rule(rule: dict, current_code: str, log_path: Path) -> str | None:
    """Check a single rule against the code and apply the fix if needed.

    Returns the (possibly updated) code.
    """
    print(f"Checking rule {rule['id']}: {rule['title']} (scope: {rule['scope']})...")
    prompt = build_prompt(rule, current_code)
    response_text = call_claude(prompt)
    parsed = parse_llm_response(response_text)

    if not parsed or not parsed[0]:
        print("  No violation found.")
        return None

    result = parsed[0]
    new_text = result.get("new", "")
    if not new_text:
        raise RuntimeError("  Violation found but new version was not provided. "
                           f"response: {result}")

    log_fix(log_path, rule, result)
    print(f"  Fixed: {result.get('description', '(no description)')}")
    return new_text


def process_file(source_path: Path) -> Path:
    """Apply all visual flow rules to the source file.

    Returns the path to the modified copy of the file.
    """
    code = source_path.read_text(encoding="utf-8")
    log_path = compute_log_path(source_path)
    if log_path.exists():
        log_path.unlink()

    output_path = source_path.with_suffix(f".after{source_path.suffix}")
    current_code = code

    any_change = False
    # LLM are not deterministic, and sometimes they don't find a rule violation on the first try
    # but only on the second try. So we try twice.
    # Also, after a change by one rule, a new opportunity to apply an earlier rule arises.
    repetitions = _CONFIG["repetitions"]
    again = repetitions
    iteration = 0
    while again > 0:
        iteration += 1
        print(f"--- Starting iteration {iteration} ---")
        changed = False
        for rule in _CONFIG["rules"]:
            while True:
                new_code = _apply_rule(rule, current_code, log_path)
                if new_code is None:
                    break
                changed = any_change = True
                current_code = new_code
        if changed:
            again = repetitions
        else:
            again -= 1

    if any_change:
        output_path.write_text(current_code, encoding="utf-8")
        print(f"\nOutput written to: {output_path}")
    else:
        print(f"\nNo change was done to: {source_path}")
    if log_path.exists():
        print(f"Log written to: {log_path}")
    return output_path


def _collect_files(source: Path) -> list[Path]:
    """Collect code files from a path.

    If a file, return it; if a directory, recurse for code files.
    """
    if source.is_file():
        return [source]
    if source.is_dir():
        return sorted(
            p for p in source.rglob("*")
            if p.is_file() and p.suffix in CODE_EXTENSIONS
        )
    return []


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply visual flow guidelines to a source file or folder using Claude."
    )
    parser.add_argument("guidelines", type=Path, help="Path to the guidelines markdown file.")
    parser.add_argument("source", type=Path, help="Path to a source code file or folder.")
    parser.add_argument("--full", action="store_true",
                        help="Use Opus instead of Sonnet and do one extra repetition.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.full:
        _CONFIG["model"] = "claude-opus-4-6"
        _CONFIG["repetitions"] = 2
    if not args.guidelines.exists():
        print(f"Error: guidelines file not found: {args.guidelines}", file=sys.stderr)
        sys.exit(1)
    if not args.source.exists():
        print(f"Error: source path not found: {args.source}", file=sys.stderr)
        sys.exit(1)
    files = _collect_files(args.source)
    if not files:
        print(f"No code files found in: {args.source}", file=sys.stderr)
        sys.exit(1)
    _CONFIG["rules"] = parse_rules(args.guidelines)
    if not _CONFIG["rules"]:
        print("No rules found in guidelines file.", file=sys.stderr)
        sys.exit(1)
    for file_path in files:
        print(f"\n{'='*60}\nProcessing: {file_path}\n{'='*60}")
        process_file(file_path)


if __name__ == "__main__":
    main()
