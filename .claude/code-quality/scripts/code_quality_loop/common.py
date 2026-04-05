"""Shared utilities for the code quality loop modules."""
from __future__ import annotations

import functools
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)

# LLM_BACKEND controls how we call Claude:
#   "api" (default) — uses the Anthropic Python SDK (requires ANTHROPIC_API_KEY, uses API credits)
#   "cli"           — shells out to `claude -p` (uses Claude Code chat account credits)
LLM_BACKEND = os.environ.get("LLM_BACKEND", "api").lower()

# Map full model names to short aliases accepted by `claude --model`.
_CLI_MODEL_ALIASES = {
    "claude-opus-4-6": "opus",
    "claude-sonnet-4-6": "sonnet",
    "claude-haiku-4-5-20251001": "haiku",
}

DEFAULT_MAX_TOKENS = 4096
DEFAULT_MODEL = os.environ.get("LLM_DEFAULT_MODEL", "claude-opus-4-6")
_CLI_TIMEOUT = int(os.environ.get("LLM_CLI_TIMEOUT", "300"))

_ANTHROPIC_CLIENT = None
_ANTHROPIC_INIT_DONE = False


def _get_anthropic_client():
    """Return the Anthropic client, initializing lazily on first call."""
    global _ANTHROPIC_CLIENT, _ANTHROPIC_INIT_DONE
    if _ANTHROPIC_INIT_DONE:
        return _ANTHROPIC_CLIENT
    _ANTHROPIC_INIT_DONE = True
    if LLM_BACKEND != "api":
        return None
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    _ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=api_key)
    return _ANTHROPIC_CLIENT


def call_llm(*, system: str, user_message: str, max_tokens: int | None,
             model: str = DEFAULT_MODEL) -> str:
    """Send a single-turn request to Claude and return the text response.

    Uses either the Anthropic API or the Claude CLI depending on LLM_BACKEND.
    """
    start = time.monotonic()
    backend = LLM_BACKEND
    try:
        if backend == "api":
            result = _call_via_api(system, user_message,
                                   max_tokens or DEFAULT_MAX_TOKENS,
                                   model)
        elif backend == "cli":
            if max_tokens:
                raise ValueError("max_tokens is not supported with the CLI backend")
            result = _call_via_cli(system, user_message,
                                   model)
        else:
            raise ValueError(f"Unknown LLM_BACKEND: {backend!r} (expected 'api' or 'cli')")
        elapsed = time.monotonic() - start
        logger.info("LLM call succeeded: model=%s backend=%s elapsed=%.1fs",
                     model, backend, elapsed)
        return result
    except Exception:
        elapsed = time.monotonic() - start
        logger.error("LLM call failed: model=%s backend=%s elapsed=%.1fs", model, backend, elapsed)
        raise


def _call_via_api(system: str, user_message: str, max_tokens: int, model: str) -> str:
    """Call Claude via the Anthropic Python SDK."""
    client = _get_anthropic_client()
    if client is None:
        raise RuntimeError("Anthropic client not initialized — is ANTHROPIC_API_KEY set?")
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


_VALID_MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")


def _call_via_cli(system: str, user_message: str, model: str) -> str:
    """Call Claude via the ``claude`` CLI subprocess."""
    cli_model = _CLI_MODEL_ALIASES.get(model, model)
    if not _VALID_MODEL_PATTERN.match(cli_model):
        raise ValueError(f"Invalid model name for CLI: {cli_model!r}")
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
            timeout=_CLI_TIMEOUT,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited with code {result.returncode}:\n"
                f"stderr: {result.stderr}\nstdout: {result.stdout}"
            )
        if result.stderr:
            logger.warning("CLI stderr (rc=0): %s", result.stderr.strip())
        return result.stdout
    except Exception:
        logger.error("CLI subprocess error: model=%s, prompt_len=%d, timeout=%d",
                      cli_model, len(user_message), _CLI_TIMEOUT)
        raise
    finally:
        try:
            os.unlink(system_file)
        except OSError:
            pass


_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(filename: str) -> str:
    """Read and return the contents of *filename* from the prompts/ directory (UTF-8)."""
    path = _PROMPTS_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Prompt file '{filename}' not found in {_PROMPTS_DIR}") from e


def issues_path(source_path: Path) -> Path:
    """Return the .issues.json sidecar path for *source_path*."""
    return source_path.parent / (source_path.stem + ".issues.json")


def decisions_path(source_path: Path) -> Path:
    """Return the .decisions.json sidecar path for *source_path*."""
    return source_path.parent / (source_path.stem + ".decisions.json")


def log_path(source_path: Path) -> Path:
    """Return the .log.jsonl sidecar path for *source_path*."""
    return source_path.parent / (source_path.stem + ".log.jsonl")


def log_append(source_path: Path, entry: dict) -> None:
    """Append a JSON log entry (with timestamp injected) to the .log.jsonl file."""
    entry = {"timestamp": now_utc(), **entry}
    try:
        with log_path(source_path).open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"Warning: failed to write log entry: {e}", file=sys.stderr)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def strip_markdown_fence(text: str) -> str:
    """Strip a markdown code fence if present; otherwise return the text unchanged."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n", 1)
        if len(lines) < 2:
            return ""
        return lines[1].rsplit("```", 1)[0]
    return text


@functools.lru_cache(maxsize=1)
def load_issue_examples() -> dict[str, dict[str, list[str]]]:
    """Load issue_examples.yaml: {type_id: {severity: [example, ...]}}."""
    text = (_PROMPTS_DIR / "issue_examples.yaml").read_text(encoding="utf-8")
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        print(f"Warning: failed to parse issue_examples.yaml: {e}", file=sys.stderr)
        return {}


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


_RE_ISSUE_HEADER = re.compile(r"^## (\S+)\s*$", re.MULTILINE)


def load_issue_types() -> list[dict[str, str]]:
    """Parse issue_types.md into a list of {"id": ..., "body": ...} dicts."""
    text = load_prompt("issue_types.md")
    matches = list(_RE_ISSUE_HEADER.finditer(text))
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
# Note: only handles an optional `json` language tag; other tags (e.g. ```python) are NOT stripped.
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

    Returns the raw JSON substring, or None if no JSON structure was found.
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


def parse_llm_response(response: str, *, label: str = "") -> list[dict[str, Any]] | None:
    """Parse Claude's JSON response.

    Returns the parsed list[dict], or None on parse failure.
    If the parsed result is a single dict, it is wrapped in a list so callers
    always receive list[dict] | None.  Empty containers ({} or [])
    are returned as-is — callers decide what empty means.
    """
    prefix = f"[{label}] " if label else ""
    json_str = _extract_json(response)
    if not json_str:
        print(f"Warning: {prefix}no JSON found in Claude response:\n"
              f"{response[:200]}", file=sys.stderr)
        return None
    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            return [parsed]
        return parsed
    except json.JSONDecodeError:
        print(f"Warning: {prefix}could not parse extracted JSON:\n{json_str[:200]}",
              file=sys.stderr)
        return None
