"""Apply visual flow guidelines to a source code file using Claude.

For each rule in the guidelines file, sends the code to Claude with the
corresponding prompt and scope, then applies the returned patch.

Usage:
    python scripts/visual_flow_applier.py <guidelines_file> <source_file>

Example:
    python scripts/visual_flow_applier.py guidelines/visual_flow.md src/app.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

import anthropic
import yaml
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPT_TEMPLATE_PATH = SCRIPT_DIR / "visual_flow_prompt.md"
_PROMPT_TEMPLATE = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
_CLIENT = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
_MODEL = "claude-opus-4-6"
_REPETITIONS = 2

VALID_SCOPES = {"local", "medium", "file"}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".kt", ".go", ".rs", ".rb",
    ".c", ".cpp", ".h", ".hpp", ".cs",
    ".swift", ".scala", ".sh", ".bash",
}


_RULES: list[dict] = []


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
            print(f"Warning: rule {rule_id} has unknown scope '{scope}', skipping.", file=sys.stderr)
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
    # parts = prompt_template.split("@@@")
    # before = parts[0].rstrip()
    # after_marker = parts[1] if len(parts) > 1 else ""  # TODO: print error to stderr if no @@@
    #
    # more_parts = after_marker.split("---", 1)
    # middle = more_parts[0].strip()
    # scope_block = _extract_scope_block(after_marker, rule["scope"])
    #
    # prompt = f"{before}\n\n{scope_block}\n\n{middle}"

    prompt_template = _PROMPT_TEMPLATE.replace("#<N>", f"#<{rule['id']}>")
    return (
        f"{prompt_template}\n\n"
        f"---\n\n"
        f"## Rule {rule['body'][3:]}\n\n"
        f"---\n\n"
        f"## Code:\n\n```\n{code}\n```"
    )


def _extract_scope_block(scope_sections: str, scope_key: str) -> str:
    """Extract the text for a given scope key from the YAML section after '---'."""
    parts = scope_sections.split("---", 1)
    if len(parts) < 2:
        print("Warning: no '---' separator found in scope sections.", file=sys.stderr)
        return ""
    scope_map = yaml.safe_load(parts[1])
    if not isinstance(scope_map, dict) or scope_key not in scope_map:
        print(f"Warning: scope '{scope_key}' not found in YAML scope definitions.", file=sys.stderr)
        return ""
    return scope_map[scope_key].strip()


_SYSTEM_PROMPT = (
    "You are a code review tool. Your output is consumed by a machine parser. "
    "You must respond with ONLY a valid JSON object, no prose, no markdown fences, no extra text."
)


def call_claude(prompt: str) -> str:
    """Send the prompt to Claude via the Anthropic API and return the response text."""
    message = _CLIENT.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _extract_json_object(text: str) -> str | None:
    """Find a JSON object in text by locating '{"key":' and brace-counting to the matching '}'."""
    text = text.strip()
    start_pos = text.find('{"rule":"')
    if start_pos < 0:
        start_pos = text.find('{\n"rule":')
        if start_pos < 0:
            print("Warning: no JSON object starting with '{\"rule\":\"' found in response.", file=sys.stderr)
            return None
    if text.endswith('}'):
        # Assume the JSON string goes till the end of the text
        return text[start_pos:]
    print("Warning: response does not end with '}', cannot extract JSON object.", file=sys.stderr)
    return None


def parse_claude_response(response: str) -> dict | None:
    """Parse Claude's JSON response. Returns None if no violation found."""
    response = response.strip()
    if response.endswith('{}'):
        return None
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        json_str = _extract_json_object(response)
        if not json_str:
            print(f"Warning: no JSON found in Claude response:\n{response[:200]}", file=sys.stderr)
            return None
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            print(f"Warning: could not parse extracted JSON:\n{json_str[:200]}", file=sys.stderr)
            return None
    return data

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
    message = _CLIENT.messages.create(
        model=_MODEL,
        max_tokens=16,
        system=_APPROVAL_SYSTEM_PROMPT.strip(),
        messages=[{"role": "user", "content": content}],
    )
    answer = message.content[0].text.strip().upper()
    return answer.startswith("YES")


def _fix_hunk_headers(diff_text: str) -> str:
    """Recalculate hunk headers in a unified diff, since LLMs often get the line counts wrong."""
    lines = diff_text.splitlines(keepends=True)
    result = []
    hunk_start = None
    old_count = 0
    new_count = 0

    for i, line in enumerate(lines):
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


def _apply_rule(rule: dict, current_code: str,
                source_path: Path, log_path: Path) -> str | None:
    """Check a single rule against the code and apply the fix if needed. Returns the (possibly updated) code."""
    print(f"Checking rule {rule['id']}: {rule['title']} (scope: {rule['scope']})...")
    prompt = build_prompt(rule, current_code)
    response_text = call_claude(prompt)
    result = parse_claude_response(response_text)

    if result is None:
        print(f"  No violation found.")
        return None

    new_text = result.get("new", "")
    if not new_text:
        print(f"  Violation found but new version was not provided.", file=sys.stderr)
        return current_code

    # if not _approve_change(diff_text):
    #     print(f"  Change was not approved")
    #     return current_code

    # patched = apply_patch(current_code, diff_text, source_path)
    # if patched is None:
    #     print(f"  Could not apply patch for rule {rule['id']}.", file=sys.stderr)
    #     return current_code

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
    repetitions = _REPETITIONS
    again = repetitions
    iteration = 0
    while again > 0:
        iteration += 1
        print(f"--- Starting iteration {iteration} ---")
        changed = False
        for rule in _RULES:
            while True:
                new_code = _apply_rule(rule, current_code, source_path, log_path)
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
    """Collect code files from a path. If a file, return it; if a directory, recurse for code files."""
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
    parser.add_argument("--cheap", action="store_true",
                        help="Use Sonnet instead of Opus and only 1 repetition.")
    return parser.parse_args()


def main() -> None:
    global _MODEL, _REPETITIONS
    args = _parse_args()
    if args.cheap:
        _MODEL = "claude-sonnet-4-6"
        _REPETITIONS = 1
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
    global _RULES
    _RULES = parse_rules(args.guidelines)
    if not _RULES:
        print("No rules found in guidelines file.", file=sys.stderr)
        sys.exit(1)
    for file_path in files:
        print(f"\n{'='*60}\nProcessing: {file_path}\n{'='*60}")
        process_file(file_path)


if __name__ == "__main__":
    main()
