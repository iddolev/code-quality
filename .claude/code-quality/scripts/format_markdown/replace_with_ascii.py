"""Rule 1: Replace smart/curly quotes with ASCII equivalents."""

from __future__ import annotations

from markdown_formatter import MarkdownFormatter

SMART_QUOTES = {
    "\u2018": "'",   # left single curly quote
    "\u2019": "'",   # right single curly quote
    "\u201C": '"',   # left double curly quote
    "\u201D": '"',   # right double curly quote
}

_SMART_QUOTE_TABLE = str.maketrans(SMART_QUOTES)


class ReplaceWithAscii(MarkdownFormatter):
    """Replace smart/curly quotes with their ASCII equivalents."""

    def apply(self, text: str) -> str:
        return text.translate(_SMART_QUOTE_TABLE)
