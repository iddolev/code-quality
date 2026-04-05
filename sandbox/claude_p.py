import os
import subprocess
import tempfile
from pathlib import Path


USER_MESSAGE = Path('sandbox/_user_message.txt').read_text(encoding='utf-8')
SYSTEM_MESSAGE = Path('sandbox/_system_message.txt').read_text(encoding='utf-8')


def call_via_cli(system: str, user_message: str) -> str:
    cli_model = 'opus'
    # Write system prompt to a temp file to avoid shell quoting issues with long prompts.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(system)
        system_file = f.name
    try:
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
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited with code {result.returncode}:\n"
                f"stderr: {result.stderr}\nstdout: {result.stdout}"
            )
        return result.stdout
    finally:
        os.unlink(system_file)


if __name__ == '__main__':
    system_prompt = "You are a helpful assistant for testing the claude CLI integration."
    user_message = "What is 2 + 2?"
    response = call_via_cli(SYSTEM_MESSAGE, USER_MESSAGE)
    print("Response from Claude:")
    print(response)
