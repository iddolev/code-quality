"""Tests for shared helpers in the MarkdownFormatter base class."""

from markdown_formatter import MarkdownFormatter


# MarkdownFormatter is abstract — use a trivial concrete subclass for testing.
class _Stub(MarkdownFormatter):
    def apply(self, text: str) -> str:
        return text


_s = _Stub()


# -- check_code_fence ---------------------------------------------------------

class TestCheckCodeFence:
    def test_no_fence_returns_current(self):
        assert _s.check_code_fence("just text", None) is None
        assert _s.check_code_fence("just text", "```") == "```"

    def test_opening_backtick_fence(self):
        assert _s.check_code_fence("```", None) == "```"
        assert _s.check_code_fence("```python", None) == "```"

    def test_closing_backtick_fence(self):
        assert _s.check_code_fence("```", "```") is None

    def test_longer_close_accepted(self):
        assert _s.check_code_fence("````", "```") is None

    def test_shorter_close_rejected(self):
        assert _s.check_code_fence("```", "````") == "````"

    def test_tilde_fence(self):
        assert _s.check_code_fence("~~~", None) == "~~~"
        assert _s.check_code_fence("~~~", "~~~") is None

    def test_mismatched_char_does_not_close(self):
        assert _s.check_code_fence("~~~", "```") == "```"
        assert _s.check_code_fence("```", "~~~") == "~~~"

    def test_indented_fence(self):
        assert _s.check_code_fence("  ```", None) == "```"


# -- is_code_fence_line -------------------------------------------------------

class TestIsCodeFenceLine:
    def test_backtick(self):
        assert _s.is_code_fence_line("```") is True
        assert _s.is_code_fence_line("```python") is True

    def test_tilde(self):
        assert _s.is_code_fence_line("~~~") is True

    def test_not_fence(self):
        assert _s.is_code_fence_line("hello") is False
        assert _s.is_code_fence_line("`` not a fence ``") is False


# -- list detection ------------------------------------------------------------

class TestListDetection:
    def test_bulleted_dash(self):
        assert _s.is_list_item_start("- item") is True

    def test_bulleted_asterisk(self):
        assert _s.is_list_item_start("* item") is True

    def test_bulleted_plus(self):
        assert _s.is_list_item_start("+ item") is True

    def test_numbered_dot(self):
        assert _s.is_list_item_start("1. item") is True

    def test_numbered_paren(self):
        assert _s.is_list_item_start("2) item") is True

    def test_indented_list_item(self):
        assert _s.is_list_item_start("  - nested") is True
        assert _s.is_list_item_start("    1. nested") is True

    def test_not_list(self):
        assert _s.is_list_item_start("hello") is False
        assert _s.is_list_item_start("") is False

    def test_match_list_item_returns_match_or_none(self):
        assert _s.match_list_item("- item") is not None
        assert _s.match_list_item("hello") is None


# -- list_continuation_indent --------------------------------------------------

class TestListContinuationIndent:
    def test_bulleted(self):
        assert _s.list_continuation_indent("- item") == "  "

    def test_numbered(self):
        assert _s.list_continuation_indent("1. item") == "   "

    def test_indented_bullet(self):
        assert _s.list_continuation_indent("  - item") == "    "

    def test_non_list_falls_back_to_detect_indent(self):
        assert _s.list_continuation_indent("    text") == "    "


# -- detect_indent -------------------------------------------------------------

class TestDetectIndent:
    def test_no_indent(self):
        assert _s.detect_indent("hello") == ""

    def test_spaces(self):
        assert _s.detect_indent("    hello") == "    "

    def test_tabs(self):
        assert _s.detect_indent("\thello") == "\t"

    def test_empty_line(self):
        assert _s.detect_indent("") == ""


# -- is_blank ------------------------------------------------------------------

class TestIsBlank:
    def test_empty(self):
        assert _s.is_blank("") is True

    def test_whitespace_only(self):
        assert _s.is_blank("   ") is True

    def test_content(self):
        assert _s.is_blank("text") is False
