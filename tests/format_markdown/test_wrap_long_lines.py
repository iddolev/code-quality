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


class TestDoubleIndentBug:
    """Issues #1, #4, #8: textwrap.fill double-applies indentation."""

    def test_indented_line_not_doubled(self):
        text = "    " + _long()
        result = _rule.apply(text)
        first_line = result.splitlines()[0]
        # First line should have exactly 4 spaces of indent, not 8
        assert first_line.startswith("    ")
        assert not first_line.startswith("        ")


class TestTrailingNewline:
    """Issue #2: trailing newline lost after splitlines join."""

    def test_trailing_newline_preserved(self):
        text = "short line\n"
        result = _rule.apply(text)
        assert result.endswith("\n")

    def test_trailing_newline_preserved_long(self):
        text = _long() + "\n"
        result = _rule.apply(text)
        assert result.endswith("\n")


class TestMultipleUrlLine:
    """Issue #3: url line check fails with multiple long URLs."""

    def test_line_with_two_moderate_urls_not_wrapped(self):
        # Two URLs each ~90 chars; removing the longest still leaves >120 due to the other URL
        url1 = "https://example.com/" + "a" * 90
        url2 = "https://other.com/" + "b" * 90
        prose = "some words here"
        text = f"See {url1} {prose} {url2}"
        assert len(text) > MAX_LINE_LENGTH
        # Removing the longest URL still leaves the other URL + prose > 120
        longest = max(url1, url2, key=len)
        without_longest = text.replace(longest, "", 1)
        assert len(without_longest) > MAX_LINE_LENGTH, "test setup: removing longest URL must still exceed limit"
        # But removing ALL URLs leaves short text
        import re
        without_all = re.sub(r"https?://\S+", "", text)
        assert len(without_all) <= MAX_LINE_LENGTH, "test setup: removing all URLs must be under limit"
        result = _rule.apply(text)
        assert result == text


class TestListMarkerPreserved:
    """Issue #10: list continuation indent includes marker in indent width."""

    def test_indented_numbered_item_preserves_marker(self):
        # Indented numbered items: detect_indent returns "  " but the text also
        # contains "  ", causing double-indentation on the first line
        item = "  1. " + _long()
        result = _rule.apply(item)
        first_line = result.splitlines()[0]
        assert first_line.startswith("  1. "), f"Expected '  1. ' prefix, got {repr(first_line[:10])}"
        # Should not have doubled indent
        assert not first_line.startswith("    1."), f"First line has doubled indent: {repr(first_line[:10])}"

    def test_indented_bullet_preserves_marker(self):
        item = "  - " + _long()
        result = _rule.apply(item)
        first_line = result.splitlines()[0]
        assert first_line.startswith("  - ")
        # Continuation lines should align with content after marker
        for cont in result.splitlines()[1:]:
            assert cont.startswith("    ")



class TestMarkdownLinkNotSplit:
    """Issue #13: textwrap splits inline markdown links across lines."""

    def test_inline_link_not_broken(self):
        link = "[some long link text here](https://example.com/page)"
        # Build a line that's long enough to wrap, with the link in the middle
        padding = "word " * 15
        text = f"{padding}{link} {padding}"
        assert len(text) > MAX_LINE_LENGTH
        result = _rule.apply(text)
        # The link must appear intact on one of the result lines
        assert any(link in line for line in result.splitlines()), \
            f"Link was split across lines:\n{result}"

    def test_image_reference_not_broken(self):
        img = "![alt text with spaces](https://example.com/image.png)"
        padding = "word " * 15
        text = f"{padding}{img} {padding}"
        assert len(text) > MAX_LINE_LENGTH
        result = _rule.apply(text)
        assert any(img in line for line in result.splitlines()), \
            f"Image ref was split across lines:\n{result}"


class TestNulCharPreserved:
    """Issue #15: NUL placeholder must not corrupt input containing NUL."""

    def test_nul_in_input_preserved(self):
        # A line with a legitimate NUL byte should not have it turned into a space
        text = "some text \x00 more text " + _long()
        result = _rule.apply(text)
        assert "\x00" in result, "NUL byte was corrupted during wrapping"


class TestBlockquoteWrapping:
    """Issue #22: blockquote lines not handled during wrapping."""

    def test_blockquote_continuation_has_prefix(self):
        text = "> " + _long()
        result = _rule.apply(text)
        for line in result.splitlines():
            assert line.startswith("> "), \
                f"Blockquote continuation missing '> ' prefix: {repr(line[:10])}"

    def test_nested_blockquote_continuation(self):
        text = ">> " + _long()
        result = _rule.apply(text)
        for line in result.splitlines():
            assert line.startswith(">> "), \
                f"Nested blockquote continuation missing '>> ' prefix: {repr(line[:10])}"


