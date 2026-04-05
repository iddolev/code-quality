"""Shared utilities for the code quality loop modules."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[4] / ".env")

# LLM_BACKEND controls how we call Claude:
#   "api" (default) — uses the Anthropic Python SDK (requires ANTHROPIC_API_KEY, uses API credits)
#   "cli"           — shells out to `claude -p` (uses Claude Code chat account credits)
LLM_BACKEND = os.environ.get("LLM_BACKEND", "api").lower()

_anthropic_client = None

if LLM_BACKEND == "api":
    import anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if "pytest" not in sys.modules:
            # Skip fatal exit during tests — tests may mock the client or use the "cli" backend
            print("Error: ANTHROPIC_API_KEY not set in environment", file=sys.stderr)
            sys.exit(1)
    else:
        _anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# Map full model names to short aliases accepted by `claude --model`.
_CLI_MODEL_ALIASES = {
    "claude-opus-4-6": "opus",
    "claude-sonnet-4-6": "sonnet",
    "claude-haiku-4-5-20251001": "haiku",
}


def call_llm(*, system: str, user_message: str, max_tokens: int = 4096,
             model: str = "claude-opus-4-6") -> str:
    """Send a single-turn request to Claude and return the text response.

    Uses either the Anthropic API or the Claude CLI depending on LLM_BACKEND.
    """
    if LLM_BACKEND == "api":
        return _call_via_api(system, user_message, max_tokens, model)
    if LLM_BACKEND == "cli":
        return _call_via_cli(system, user_message, model)
    raise ValueError(f"Unknown LLM_BACKEND: {LLM_BACKEND!r} (expected 'api' or 'cli')")


def _call_via_api(system: str, user_message: str, max_tokens: int, model: str) -> str:
    response = _anthropic_client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def _call_via_cli(system: str, user_message: str, model: str) -> str:
    cli_model = _CLI_MODEL_ALIASES.get(model, model)
    # Write system prompt to a temp file to avoid shell quoting issues with long prompts.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(system)
        system_file = f.name
    try:
        # Remove ANTHROPIC_API_KEY from the subprocess env so the CLI uses
        # chat-account credits instead of API billing.
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        result = subprocess.run(
            ["claude", "-p",
             "--model", cli_model,
             "--system-prompt-file", system_file,
             "--no-session-persistence",
             "--output-format", "text"],
            input=user_message,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited with code {result.returncode}:\n"
                f"stderr: {result.stderr}\nstdout: {result.stdout}"
            )
        return result.stdout
    finally:
        os.unlink(system_file)


_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def issues_path(source_path: Path) -> Path:
    return source_path.with_suffix("").with_suffix(".issues.json")


def decisions_path(source_path: Path) -> Path:
    return source_path.with_suffix("").with_suffix(".decisions.json")


def log_path(source_path: Path) -> Path:
    return source_path.with_suffix("").with_suffix(".log.jsonl")


def log_append(source_path: Path, entry: dict) -> None:
    """Append a JSON log entry (with timestamp injected) to the .log.jsonl file."""
    entry = {"timestamp": now_utc(), **entry}
    with log_path(source_path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def strip_markdown_fence(text: str) -> str:
    """Strip a markdown code fence if present; otherwise return the text unchanged."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n", 1)
        if len(lines) < 2:
            return text
        return lines[1].rsplit("```", 1)[0]
    return text


def load_issue_examples() -> dict[str, dict[str, list[str]]]:
    """Load issue_examples.yaml: {type_id: {severity: [example, ...]}}."""
    text = (_PROMPTS_DIR / "issue_examples.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


def format_examples_for_type(all_examples: dict[str, dict[str, list[str]]],
                             type_id: str) -> str:
    """Format examples for a single issue type as markdown."""
    type_examples = all_examples.get(type_id, {})
    if not type_examples:
        return ""
    lines = ["## Examples"]
    for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        examples = type_examples.get(severity, [])
        if examples:
            lines.append(f"\n{severity}:\n")
            for ex in examples:
                lines.append(f"- {ex}")
    return "\n".join(lines)


def load_issue_types() -> list[dict[str, str]]:
    """Parse issue_types.md into a list of {"id": ..., "body": ...} dicts."""
    text = load_prompt("issue_types.md")
    header_pattern = re.compile(r"^## (\S+)\s*$", re.MULTILINE)
    matches = list(header_pattern.finditer(text))
    result = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        result.append({
            "id": match.group(1),
            "body": text[start:end].strip(),
        })
    return result


# [\s\S]*? matches any char including newlines.
# The *? makes it non-greedy, so it matches the smallest stretch between ``` pairs
# rather than gobbling from the first ``` to the very last ``` in the text.
_RE_FENCE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)```")
_RE_JSON_OBJ_START = re.compile(r'\{\s*"(?:rule|fingerprint)":')
_RE_JSON_ARRAY_START = re.compile(r'\[\s*\{\s*"(?:rule|fingerprint)":')


def _extract_json(text: str) -> str | None:
    """Extract JSON from *text* that may contain prose and/or markdown fences.

    The real answer is always at the END (Claude may output a possibly fenced block, then
    correct itself and output something else afterwards).  Strategy:
      1. Unwrap all markdown fences: replace ```(json)?...``` with their content.
      2. Strip and search backwards from the end for a JSON start: ``[{``, ``[\\n{``,
         ``{``, or ``{\\n`` — then take from that start to the end of the string.
    """
    # 1. Unwrap all fenced blocks, keeping only their content.
    unwrapped = _RE_FENCE.sub(r"\1", text).strip()

    # 2. Check for empty containers at the very end (e.g. "...corrected.\n[]")
    if unwrapped.endswith("[]") or unwrapped.endswith("{}"):
        return unwrapped[-2:]

    # 3. Must end with } or ] — otherwise there's no JSON at the end.
    if unwrapped.endswith("}"):
        pattern = _RE_JSON_OBJ_START
    elif unwrapped.endswith("]"):
        pattern = _RE_JSON_ARRAY_START
    else:
        return None

    # Find the last occurrence (the real answer, not earlier prose).
    matches = list(pattern.finditer(unwrapped))
    return unwrapped[matches[-1].start():] if matches else None


def parse_llm_response(response: str) -> dict | list[dict[str, Any]] | None:
    """Parse Claude's JSON response.

    Returns the parsed dict/list, or None on parse failure.
    Empty containers ({} or []) are returned as-is — callers decide what empty means.
    """
    json_str = _extract_json(response)
    if not json_str:
        print(f"Warning: no JSON found in Claude response:\n{response[:200]}", file=sys.stderr)
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        print(f"Warning: could not parse extracted JSON:\n{json_str[:200]}", file=sys.stderr)
        return None
