"""Tests for format_html module."""

import pytest

from ..format_html import (
    html_code,
    html_heading,
    html_link,
    html_list,
    html_p,
    markdown_to_html,
    process_inline_formatting,
)


class TestHtmlHelpers:
    """Test HTML helper functions."""

    def test_html_p(self):
        """Test paragraph creation."""
        assert html_p("Hello") == "<p>Hello</p>"
        assert html_p("Hello <strong>world</strong>") == "<p>Hello <strong>world</strong></p>"

    def test_html_heading(self):
        """Test heading creation."""
        assert html_heading("Title", 1) == "<h1>Title</h1>"
        assert html_heading("Subtitle", 2) == "<h2>Subtitle</h2>"
        assert html_heading("Deep", 6) == "<h6>Deep</h6>"

    def test_html_heading_level_clamping(self):
        """Test heading level is clamped to 1-6."""
        assert html_heading("Test", 0) == "<h1>Test</h1>"
        assert html_heading("Test", 10) == "<h6>Test</h6>"

    def test_html_list_unordered(self):
        """Test unordered list creation."""
        items = ["First", "Second", "Third"]
        result = html_list(items, ordered=False)
        assert result == "<ul><li>First</li><li>Second</li><li>Third</li></ul>"

    def test_html_list_ordered(self):
        """Test ordered list creation."""
        items = ["Step 1", "Step 2"]
        result = html_list(items, ordered=True)
        assert result == "<ol><li>Step 1</li><li>Step 2</li></ol>"

    def test_html_code_without_language(self):
        """Test code block without language."""
        result = html_code("print('hello')")
        assert result == "<pre><code>print('hello')</code></pre>"

    def test_html_code_with_language(self):
        """Test code block with language."""
        result = html_code("print('hello')", "python")
        assert result == '<pre><code class="language-python">print(\'hello\')</code></pre>'

    def test_html_link(self):
        """Test link creation."""
        result = html_link("Click here", "https://example.com")
        assert result == '<a href="https://example.com">Click here</a>'


class TestInlineFormatting:
    """Test inline markdown formatting."""

    def test_bold_text(self):
        """Test bold formatting."""
        assert process_inline_formatting("**bold**") == "<strong>bold</strong>"
        assert process_inline_formatting("text **bold** text") == "text <strong>bold</strong> text"

    def test_italic_text(self):
        """Test italic formatting."""
        assert process_inline_formatting("*italic*") == "<em>italic</em>"
        assert process_inline_formatting("text *italic* text") == "text <em>italic</em> text"

    def test_inline_code(self):
        """Test inline code formatting."""
        assert process_inline_formatting("`code`") == "<code>code</code>"
        assert process_inline_formatting("run `npm install` command") == "run <code>npm install</code> command"

    def test_links(self):
        """Test markdown link conversion."""
        result = process_inline_formatting("[text](https://example.com)")
        assert result == '<a href="https://example.com">text</a>'

    def test_combined_formatting(self):
        """Test multiple inline formats together."""
        text = "This is **bold** and *italic* with `code`"
        result = process_inline_formatting(text)
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result
        assert "<code>code</code>" in result


class TestMarkdownToHtml:
    """Test full markdown to HTML conversion."""

    def test_simple_paragraph(self):
        """Test simple paragraph conversion."""
        result = markdown_to_html("Hello world")
        assert "<p>Hello world</p>" in result

    def test_headings(self, sample_markdown):
        """Test heading conversion."""
        result = markdown_to_html(sample_markdown)
        assert "<h1>Heading 1</h1>" in result
        assert "<h2>Heading 2</h2>" in result

    def test_lists(self, sample_markdown):
        """Test list conversion."""
        result = markdown_to_html(sample_markdown)
        assert "<ul>" in result
        assert "<li>List item 1</li>" in result
        assert "<ol>" in result
        assert "<li>Numbered item 1</li>" in result

    def test_code_blocks(self, sample_markdown):
        """Test code block conversion."""
        result = markdown_to_html(sample_markdown)
        assert "<pre><code" in result
        assert 'class="language-python"' in result

    def test_links(self, sample_markdown):
        """Test link conversion."""
        result = markdown_to_html(sample_markdown)
        assert '<a href="https://example.com">Link text</a>' in result

    def test_inline_formatting(self, sample_markdown):
        """Test inline bold and italic."""
        result = markdown_to_html(sample_markdown)
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result

    def test_empty_input(self):
        """Test empty markdown."""
        result = markdown_to_html("")
        assert result == ""

    def test_whitespace_only(self):
        """Test whitespace-only input."""
        result = markdown_to_html("   \n\n   ")
        # Should produce minimal output or empty
        assert len(result) < 50


class TestCLI:
    """Test command-line interface."""

    def test_cli_help(self):
        """Test CLI help output."""
        # This would require subprocess testing
        # Placeholder for CLI integration tests
        pass
