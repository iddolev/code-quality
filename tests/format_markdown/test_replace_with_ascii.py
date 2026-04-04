"""Tests for ReplaceWithAscii (Rule 1)."""

from scripts.format_markdown.replace_with_ascii import ReplaceWithAscii

_rule = ReplaceWithAscii()


class TestReplaceWithAscii:
    def test_left_double_quote(self):
        assert _rule.apply("\u201Chello") == '"hello'

    def test_right_double_quote(self):
        assert _rule.apply("hello\u201D") == 'hello"'

    def test_left_single_quote(self):
        assert _rule.apply("\u2018hi") == "'hi"

    def test_right_single_quote(self):
        assert _rule.apply("hi\u2019") == "hi'"

    def test_mixed_quotes(self):
        assert _rule.apply("\u201Chello\u201D and \u2018world\u2019") == '"hello" and \'world\''

    def test_no_smart_quotes(self):
        text = 'plain "text" with \'normal\' quotes'
        assert _rule.apply(text) == text

    def test_empty_string(self):
        assert _rule.apply("") == ""

    def test_multiline(self):
        text = "\u201CLine one\u201D\n\u2018Line two\u2019"
        assert _rule.apply(text) == '"Line one"\n\'Line two\''

    def test_multiple_on_same_line(self):
        assert _rule.apply("\u201Ca\u201D \u201Cb\u201D") == '"a" "b"'
