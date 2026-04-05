"""Abstract base class for markdown formatting rules."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

_CODE_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_BULLETED_ITEM_RE = re.compile(r"^(\s*[-*+] )")
_NUMBERED_ITEM_RE = re.compile(r"^(\s*\d+[.)]\s)")


class MarkdownFormatter(ABC):
    """A single markdown formatting rule.

    Each subclass implements one formatting concern.  The ``apply`` method
    receives the full file content as a string and returns the transformed
    content.

    Shared helpers for code-fence tracking, list detection and indentation
    live here so that line-based rules can reuse them.
    """

    @abstractmethod
    def apply(self, text: str) -> str:
        """Apply this formatting rule to *text* and return the result."""

    # -- code-fence tracking --------------------------------------------------

    @staticmethod
    def check_code_fence(line: str, current_fence: str | None) -> str | None:
        """Track code fence state using matching markers.

        Returns the updated fence marker: a non-None string when inside a
        fenced block, or None when outside.  A closing fence must use the same
        character (backtick or tilde) and be *at least* as long as the opening
        fence.
        """
        m = _CODE_FENCE_RE.match(line)
        if not m:
            return current_fence

        marker = m.group(1)
        fence_char = marker[0]
        fence_len = len(marker)

        if current_fence is None:
            return marker

        open_char = current_fence[0]
        open_len = len(current_fence)
        if fence_char == open_char and fence_len >= open_len:
            return None
        return current_fence

    @staticmethod
    def is_code_fence_line(line: str) -> bool:
        return bool(_CODE_FENCE_RE.match(line))

    # -- list detection --------------------------------------------------------

    @staticmethod
    def match_list_item(line: str):
        return _BULLETED_ITEM_RE.match(line) or _NUMBERED_ITEM_RE.match(line)

    @staticmethod
    def is_list_item_start(line: str) -> bool:
        return bool(_BULLETED_ITEM_RE.match(line) or _NUMBERED_ITEM_RE.match(line))

    @staticmethod
    def list_continuation_indent(line: str) -> str:
        """Return the indent string for continuation lines of a list item."""
        match = _BULLETED_ITEM_RE.match(line) or _NUMBERED_ITEM_RE.match(line)
        if match:
            return " " * len(match.group(1))
        return MarkdownFormatter.detect_indent(line)

    # -- indentation / blank helpers -------------------------------------------

    @staticmethod
    def detect_indent(line: str) -> str:
        return line[:len(line) - len(line.lstrip())]

    @staticmethod
    def is_blank(line: str) -> bool:
        return not line.strip()
