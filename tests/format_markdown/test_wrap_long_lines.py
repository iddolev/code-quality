"""Tests for WrapLongLines (Rule 2)."""

from scripts.format_markdown.wrap_long_lines import WrapLongLines, MAX_LINE_LENGTH

_rule = WrapLongLines()


def _long(n: int = MAX_LINE_LENGTH + 1) -> str:
    """Return a string of n characters made of short words."""
    words = "word " * (n // 5 + 1)
    return words[:n]


class TestShortLinesUnchanged:
    def test_short_line(self):
        text = "short line"
        assert _rule.apply(text) == text

    def test_exactly_at_limit(self):
        text = "x" * MAX_LINE_LENGTH
        assert _rule.apply(text) == text

    def test_empty(self):
        assert _rule.apply("") == ""


class TestLongLinesWrapped:
    def test_wraps_long_line(self):
        text = _long()
        result = _rule.apply(text)
        for line in result.splitlines():
            assert len(line) <= MAX_LINE_LENGTH

    def test_preserves_indent(self):
        text = "    " + _long()
        result = _rule.apply(text)
        for line in result.splitlines():
            assert line.startswith("    ")


class TestCodeBlocksSkipped:
    def test_long_line_inside_backtick_fence(self):
        long = "x " * 100
        text = f"```\n{long}\n```"
        assert _rule.apply(text) == text

    def test_long_line_inside_tilde_fence(self):
        long = "x " * 100
        text = f"~~~\n{long}\n~~~"
        assert _rule.apply(text) == text

    def test_fence_line_itself_not_wrapped(self):
        fence = "```" + "python" + " " * 200
        text = f"{fence}\ncode\n```"
        result = _rule.apply(text)
        assert result.splitlines()[0] == fence


class TestTableRowsSkipped:
    def test_long_table_row(self):
        row = "| " + "cell | " * 30 + "|"
        assert len(row) > MAX_LINE_LENGTH
        assert _rule.apply(row) == row


class TestUrlLinesSkipped:
    def test_line_long_only_because_of_url(self):
        url = "https://example.com/" + "a" * 150
        text = f"See {url}"
        assert len(text) > MAX_LINE_LENGTH
        assert _rule.apply(text) == text

    def test_long_line_without_url_still_wrapped(self):
        text = _long()
        result = _rule.apply(text)
        assert len(result.splitlines()) > 1


class TestListItemWrapping:
    def test_bulleted_item_continuation_indent(self):
        item = "- " + _long()
        result = _rule.apply(item)
        lines = result.splitlines()
        assert lines[0].startswith("- ")
        for cont in lines[1:]:
            assert cont.startswith("  ")

    def test_numbered_item_continuation_indent(self):
        item = "1. " + _long()
        result = _rule.apply(item)
        lines = result.splitlines()
        assert lines[0].startswith("1. ")
        for cont in lines[1:]:
            assert cont.startswith("   ")


class TestMultilineInput:
    def test_mix_of_short_and_long(self):
        short = "short"
        long = _long()
        text = f"{short}\n{long}"
        result = _rule.apply(text)
        result_lines = result.splitlines()
        assert result_lines[0] == short
        assert len(result_lines) > 2
