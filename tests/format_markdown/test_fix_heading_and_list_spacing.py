"""Tests for FixHeadingAndListSpacing (Rules 3-5)."""

from scripts.format_markdown.fix_heading_and_list_spacing import FixHeadingAndListSpacing

_rule = FixHeadingAndListSpacing()


# -- Rule 3: heading followed by blank line ------------------------------------

class TestHeadingBlankLine:
    def test_inserts_blank_after_heading(self):
        text = "# Title\nContent"
        result = _rule.apply(text)
        assert result == "# Title\n\nContent"

    def test_already_has_blank_after_heading(self):
        text = "# Title\n\nContent"
        assert _rule.apply(text) == text

    def test_all_heading_levels(self):
        for level in range(1, 7):
            hashes = "#" * level
            text = f"{hashes} Heading\nContent"
            result = _rule.apply(text)
            assert f"{hashes} Heading\n\nContent" == result

    def test_heading_at_end_of_file(self):
        text = "# Title"
        assert _rule.apply(text) == text

    def test_consecutive_headings(self):
        text = "# First\n## Second\nContent"
        result = _rule.apply(text)
        assert result == "# First\n\n## Second\n\nContent"


# -- Rule 4: list preceded by blank line ---------------------------------------

class TestListPrecededByBlank:
    def test_inserts_blank_before_list(self):
        text = "Paragraph\n- item 1\n- item 2"
        result = _rule.apply(text)
        assert result == "Paragraph\n\n- item 1\n- item 2"

    def test_already_has_blank_before_list(self):
        text = "Paragraph\n\n- item 1"
        assert _rule.apply(text) == text

    def test_numbered_list(self):
        text = "Paragraph\n1. first\n2. second"
        result = _rule.apply(text)
        assert result == "Paragraph\n\n1. first\n2. second"

    def test_list_right_after_heading_no_extra_blank(self):
        # Heading already gets a blank line; no double blank expected.
        text = "# Title\n- item"
        result = _rule.apply(text)
        assert result == "# Title\n\n- item"


# -- Rule 5: list followed by blank line --------------------------------------

class TestListFollowedByBlank:
    def test_inserts_blank_after_list(self):
        text = "- item 1\n- item 2\nParagraph"
        result = _rule.apply(text)
        assert result == "- item 1\n- item 2\n\nParagraph"

    def test_already_has_blank_after_list(self):
        text = "- item 1\n\nParagraph"
        assert _rule.apply(text) == text

    def test_list_at_end_of_file(self):
        text = "- item"
        assert _rule.apply(text) == text


# -- frontmatter ---------------------------------------------------------------

class TestFrontmatter:
    def test_skips_frontmatter(self):
        text = "---\ntitle: test\n---\n# Heading\nContent"
        result = _rule.apply(text)
        assert result == "---\ntitle: test\n---\n# Heading\n\nContent"

    def test_no_frontmatter(self):
        text = "# Title\nContent"
        result = _rule.apply(text)
        assert result == "# Title\n\nContent"


# -- code blocks ---------------------------------------------------------------

class TestCodeBlocks:
    def test_heading_inside_code_block_not_modified(self):
        text = "```\n# not a heading\ntext\n```"
        assert _rule.apply(text) == text

    def test_list_inside_code_block_not_modified(self):
        text = "```\n- not a list\ntext\n```"
        assert _rule.apply(text) == text


# -- mixed scenarios -----------------------------------------------------------

class TestMixed:
    def test_heading_then_list(self):
        text = "# Title\n- item"
        result = _rule.apply(text)
        assert result == "# Title\n\n- item"

    def test_paragraph_list_paragraph(self):
        text = "Before\n- item\nAfter"
        result = _rule.apply(text)
        assert result == "Before\n\n- item\n\nAfter"

    def test_no_duplicate_blanks(self):
        text = "Paragraph\n\n\n- item"
        result = _rule.apply(text)
        assert "\n\n\n" not in result

    def test_empty_input(self):
        assert _rule.apply("") == ""

    def test_indented_list(self):
        text = "Paragraph\n  - nested item\nAfter"
        result = _rule.apply(text)
        assert "Paragraph\n\n  - nested item\n\nAfter" == result
