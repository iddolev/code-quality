"""LLM invocation utilities: call Claude via the Anthropic API or the Claude CLI."""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import time

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

DEFAULT_MAX_TOKENS = 16000
DEFAULT_MODEL = os.environ.get("LLM_DEFAULT_MODEL", "claude-sonnet-4-6")
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


def call_llm(*, system_message: str, user_message: str,
             max_tokens: int = DEFAULT_MAX_TOKENS,
             model: str = DEFAULT_MODEL) -> str:
    """Send a single-turn request to Claude and return the text response.

    Uses either the Anthropic API or the Claude CLI depending on LLM_BACKEND.
    """
    start = time.monotonic()
    backend = LLM_BACKEND
    try:
        if backend == "api":
            result = _call_via_api(system_message, user_message, max_tokens, model)
        elif backend == "cli":
            result = _call_via_cli(system_message, user_message, model)
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


def _call_via_api(system_message: str, user_message: str, max_tokens: int, model: str) -> str:
    """Call Claude via the Anthropic Python SDK."""
    client = _get_anthropic_client()
    if client is None:
        raise RuntimeError("Anthropic client not initialized — is ANTHROPIC_API_KEY set?")
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_message,
        messages=[{"role": "user", "content": user_message}],
    )
    if not response.content:
        raise RuntimeError("Anthropic API returned an empty content list")
    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    if not text:
        raise RuntimeError("Anthropic API response contained no text blocks")
    return text


_VALID_MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")


def _call_via_cli(system_message: str, user_message: str, model: str) -> str:
    """Call Claude via the ``claude`` CLI subprocess."""
    cli_model = _CLI_MODEL_ALIASES.get(model, model)
    if not _VALID_MODEL_PATTERN.match(cli_model):
        raise ValueError(f"Invalid model name for CLI: {cli_model!r}")
    # Write system prompt to a temp file to avoid shell quoting issues with long prompts.
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    system_file = tmp.name
    try:
        tmp.write(system_message)
        tmp.close()
    except Exception:
        try:
            tmp.close()
        except Exception:
            pass
        try:
            os.unlink(system_file)
        except OSError:
            pass
        raise
    try:
        # Remove ANTHROPIC_API_KEY from the subprocess env so the CLI uses
        # chat-account credits instead of API billing.
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        proc = subprocess.Popen(
            ["claude", "-p",
             "--model", cli_model,
             "--system-prompt-file", system_file,
             "--no-session-persistence",
             "--output-format", "text"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            stdout, stderr = proc.communicate(input=user_message, timeout=_CLI_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited with code {proc.returncode}:\n"
                f"stderr: {stderr}\nstdout: {stdout}"
            )
        if stderr:
            logger.warning("CLI stderr (rc=0): %s", stderr.strip())
        if not stdout.strip():
            raise RuntimeError(
                f"claude CLI returned empty stdout (rc=0):\nstderr: {stderr}"
            )
        return stdout
    except Exception:
        logger.error("CLI subprocess error: model=%s, prompt_len=%d, timeout=%d",
                      cli_model, len(user_message), _CLI_TIMEOUT)
        raise
    finally:
        try:
            os.unlink(system_file)
        except OSError:
            pass
