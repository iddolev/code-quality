"""LLM invocation utilities: call Claude via the Anthropic API or the Claude CLI."""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import threading
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


def _int_from_env(name: str, default: int) -> int:
    """Read an int from the environment, falling back to ``default`` on invalid values."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid value for %s=%r; falling back to default %d", name, raw, default)
        return default


DEFAULT_MAX_TOKENS = _int_from_env('LLM_MAX_TOKENS', 16000)
DEFAULT_MODEL = os.environ.get("LLM_DEFAULT_MODEL", "claude-sonnet-4-6")
_CLI_TIMEOUT = int(os.environ.get("LLM_CLI_TIMEOUT", "300"))
_CLI_PATH = os.environ.get("LLM_CLI_PATH", "claude")

_ANTHROPIC_CLIENT = None
_ANTHROPIC_INIT_DONE = False
_ANTHROPIC_INIT_LOCK = threading.Lock()


def _get_anthropic_client():
    """Return the Anthropic client, initializing lazily on first call."""
    global _ANTHROPIC_CLIENT, _ANTHROPIC_INIT_DONE
    if _ANTHROPIC_INIT_DONE and _ANTHROPIC_CLIENT is not None:
        return _ANTHROPIC_CLIENT
    with _ANTHROPIC_INIT_LOCK:
        if _ANTHROPIC_INIT_DONE and _ANTHROPIC_CLIENT is not None:
            return _ANTHROPIC_CLIENT
        if LLM_BACKEND != "api":
            _ANTHROPIC_INIT_DONE = True
            return None
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error('ANTHROPIC_API_KEY not set; cannot initialize Anthropic client')
            return None
        _ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=api_key)
        _ANTHROPIC_INIT_DONE = True
        return _ANTHROPIC_CLIENT


def call_llm(*, system_message: str, user_message: str,
             max_tokens: int = DEFAULT_MAX_TOKENS,
             model: str = DEFAULT_MODEL) -> str:
    """Send a single-turn request to Claude and return the text response.

    Uses either the Anthropic API or the Claude CLI depending on LLM_BACKEND.

    Note: ``max_tokens`` only applies to the API backend. It is silently
    ignored when ``LLM_BACKEND='cli'``, since the Claude CLI does not expose
    a max-tokens option.
    """
    if not system_message:
        raise ValueError("system_message must not be empty")
    if not user_message:
        raise ValueError("user_message must not be empty")
    start = time.monotonic()
    backend = LLM_BACKEND
    input_tokens = None
    output_tokens = None
    try:
        if backend == "api":
            result, input_tokens, output_tokens = _call_via_api(
                system_message, user_message, max_tokens, model
            )
        elif backend == "cli":
            result = _call_via_cli(system_message, user_message, model)
        else:
            raise ValueError(f"Unknown LLM_BACKEND: {backend!r} (expected 'api' or 'cli')")
        elapsed = time.monotonic() - start
        prompt_len = len(user_message)
        response_len = len(result)
        logger.info(
            "LLM call succeeded: model=%s backend=%s elapsed=%.1fs "
            "prompt_len=%d response_len=%d input_tokens=%s output_tokens=%s",
            model, backend, elapsed, prompt_len, response_len,
            input_tokens if input_tokens is not None else "n/a",
            output_tokens if output_tokens is not None else "n/a",
        )
        return result
    except Exception:
        elapsed = time.monotonic() - start
        logger.exception("LLM call failed: model=%s backend=%s elapsed=%.1fs", model, backend, elapsed)
        raise


def _call_via_api(system_message: str, user_message: str, max_tokens: int,
                  model: str) -> tuple[str, int | None, int | None]:
    """Call Claude via the Anthropic Python SDK.

    Returns a tuple ``(text, input_tokens, output_tokens)``. The token counts
    may be ``None`` if the response did not include usage information.
    """
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
        raise RuntimeError(f'Anthropic API returned empty content: model={model} stop_reason={getattr(response, "stop_reason", None)}')
    text = "".join(t for t in (getattr(b, "text", None) for b in response.content) if t is not None)
    if not text:
        raise RuntimeError(f'No text blocks; stop_reason={response.stop_reason}, block_types={[getattr(b, "type", None) for b in response.content]}')
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None) if usage is not None else None
    output_tokens = getattr(usage, "output_tokens", None) if usage is not None else None
    return text, input_tokens, output_tokens


_VALID_MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def _call_via_cli(system_message: str, user_message: str, model: str) -> str:
    """Call Claude via the ``claude`` CLI subprocess."""
    cli_model = _CLI_MODEL_ALIASES.get(model, model)
    if not _VALID_MODEL_PATTERN.match(cli_model):
        raise ValueError(f"Invalid model name for CLI: {cli_model!r}")
    # Write system prompt to a temp file to avoid shell quoting issues with long prompts.
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    system_file = tmp.name
    try:
        try:
            tmp.write(system_message)
        finally:
            tmp.close()
        # Remove ANTHROPIC_API_KEY from the subprocess env so the CLI uses
        # chat-account credits instead of API billing.
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        proc = subprocess.Popen(
            [_CLI_PATH, "-p",
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
            try:
                # Drain pipes and reap the process after killing it, with a
                # bounded wait so we don't hang here indefinitely.
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("claude CLI did not exit after kill within 5s")
            raise RuntimeError(f'claude CLI timed out after {_CLI_TIMEOUT}s for model {cli_model}') from None
        if proc.returncode != 0:
            logger.error('claude CLI failed: rc=%d model=%s stderr=%s', proc.returncode, cli_model, stderr.strip())
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
        logger.exception("CLI subprocess error: model=%s, prompt_len=%d, timeout=%d",
                      cli_model, len(user_message), _CLI_TIMEOUT)
        raise
    finally:
        try:
            os.unlink(system_file)
        except OSError as e:
            logger.warning('Failed to remove temp system prompt file %s: %s', system_file, e)
