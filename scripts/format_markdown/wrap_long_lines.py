"""Rule 2: Wrap lines longer than 120 characters.

Exceptions: table rows, lines long only because of a URL, and code blocks.
"""

from __future__ import annotations

import re
import textwrap

from scripts.format_markdown.markdown_formatter import MarkdownFormatter

MAX_LINE_LENGTH = 120
_URL_RE = re.compile(r"https?://\S+")

# Patterns for inline Markdown constructs that should not be split across lines.
_INLINE_CONSTRUCTS_RE = re.compile(
    r"!\[[^\]]*\]\([^)]*\)"   # images  ![alt](url)
    r"|\[[^\]]*\]\([^)]*\)"   # links   [text](url)
    r"|\[[^\]]*\]\[[^\]]*\]"  # ref links [text][ref]
    r"|`[^`]+`"                # inline code `code`
)

_PLACEHOLDER_CHAR = "\x00"
_TOKEN_RE = re.compile(re.escape(_PLACEHOLDER_CHAR) + r"(\d+)" + re.escape(_PLACEHOLDER_CHAR))

# Regex that captures the leading whitespace, the list marker (with its
# trailing space), and the rest of the line.  Works for ``- ``, ``* ``,
# ``+ ``, and ``1. `` / ``12) `` style markers.
_LIST_MARKER_RE = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<marker>(?:[-*+]|\d+[.)]))[ \t]+"
)

# Regex that captures a leading blockquote prefix, e.g. "> ", ">> ", "> > ".
_BLOCKQUOTE_RE = re.compile(r"^(?:>\s*)+")


class WrapLongLines(MarkdownFormatter):
    """Wrap lines exceeding 120 characters."""

    def apply(self, text: str) -> str:
        lines = text.splitlines()
        result: list[str] = []
        code_fence: str | None = None

        for line in lines:
            code_fence = self.check_code_fence(line, code_fence)
            in_code = code_fence is not None and not self.is_code_fence_line(line)

            if self.is_code_fence_line(line) or in_code or len(line) <= MAX_LINE_LENGTH:
                result.append(line)
            elif self._should_skip_wrapping(line):
                result.append(line)
            else:
                result.extend(self._wrap_single_line(line))

        output = "\n".join(result)
        if text.endswith("\n"):
            output += "\n"
        return output

    # -- private helpers -------------------------------------------------------

    @staticmethod
    def _is_table_row(line: str) -> bool:
        """Return True if the line appears to be a Markdown table row."""
        stripped = line.strip()
        return stripped.startswith("|") and stripped.endswith("|")

    @staticmethod
    def _is_url_line(line: str) -> bool:
        """True if the line is long only because it contains a URL."""
        urls = _URL_RE.findall(line)
        if not urls:
            return False
        without_urls = _URL_RE.sub('', line)
        return len(without_urls) <= MAX_LINE_LENGTH

    @classmethod
    def _should_skip_wrapping(cls, line: str) -> bool:
        """Return True if the line is a table row or is long only due to a URL."""
        return cls._is_table_row(line) or cls._is_url_line(line)

    @staticmethod
    def _protect_inline_constructs(text: str) -> tuple[str, list[str]]:
        """Replace inline Markdown constructs with unique numbered tokens.

        Returns the modified text and a list of original matched spans used
        for restoration.
        """
        originals: list[str] = []

        def _replace_with_token(m: re.Match[str]) -> str:
            idx = len(originals)
            originals.append(m.group(0))
            return f"{_PLACEHOLDER_CHAR}{idx}{_PLACEHOLDER_CHAR}"

        protected = _INLINE_CONSTRUCTS_RE.sub(_replace_with_token, text)
        return protected, originals

    @staticmethod
    def _restore_inline_constructs(text: str, originals: list[str]) -> str:
        """Restore numbered placeholder tokens back to original spans."""
        def _replace_token(m: re.Match[str]) -> str:
            return originals[int(m.group(1))]

        return _TOKEN_RE.sub(_replace_token, text)

    @staticmethod
    def _strip_blockquote_prefix(line: str) -> tuple[str, str]:
        """Strip and return the blockquote prefix and the remaining content.

        Returns a tuple of (prefix, rest) where *prefix* is the leading
        ``> `` / ``>> `` portion (empty string when the line is not a
        blockquote) and *rest* is the remainder of the line.
        """
        bq = _BLOCKQUOTE_RE.match(line)
        if bq:
            prefix = bq.group(0)
            rest = line[bq.end():]
            # Normalise: ensure the prefix ends with a single space so that
            # continuation lines look consistent.
            if not prefix.endswith(" "):
                prefix += " "
            return prefix, rest
        return "", line

    def _wrap_single_line(self, line: str) -> list[str]:
        """Wrap a single long line respecting its indentation and list-item context.

        Returns a list of wrapped line strings.
        """
        # Strip blockquote prefix first so the rest of the logic sees plain
        # content.  The prefix is re-added to every wrapped output line.
        bq_prefix, line_without_bq = self._strip_blockquote_prefix(line)

        m = _LIST_MARKER_RE.match(line_without_bq)
        if m:
            indent = m.group("indent")
            marker_and_space = line_without_bq[len(indent):m.end()]
            full_initial_indent = bq_prefix + indent + marker_and_space
            subsequent_indent = bq_prefix + indent + " " * len(marker_and_space)
            content_after_marker = line_without_bq[m.end():]
        else:
            initial_indent = self.detect_indent(line_without_bq)
            full_initial_indent = bq_prefix + initial_indent
            subsequent_indent = bq_prefix + initial_indent
            content_after_marker = line_without_bq.lstrip()

        # Protect inline constructs from being split by textwrap.
        protected, originals = self._protect_inline_constructs(content_after_marker)

        wrapped = textwrap.fill(protected,
                                width=MAX_LINE_LENGTH,
                                initial_indent=full_initial_indent,
                                subsequent_indent=subsequent_indent,
                                break_long_words=False,
                                break_on_hyphens=False)

        # Restore the protected spans.
        wrapped = self._restore_inline_constructs(wrapped, originals)
        return wrapped.split("\n")