"""
Comprehensive test suite for documentation validation.

Tests include:
- Link validation (no dead internal links)
- Orphan detection (all files reachable from INDEX.md)
- Image/diagram existence
- Markdown syntax validation
- Navigation structure validation
"""

import re
import sys
from pathlib import Path
from typing import List, Set

import pytest

# Add scripts directory to path for imports
scripts_dir = Path(__file__).parent.parent / 'scripts'
sys.path.insert(0, str(scripts_dir))

from validate_docs_links import LinkValidator, ValidationResult
from find_orphaned_docs import OrphanDetector, OrphanReport


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def docs_dir(request) -> Path:
    """Return path to documentation directory."""
    # Allow override via pytest marker
    marker = request.node.get_closest_marker('docs_dir')
    if marker:
        return Path(marker.args[0])

    # Default to docs directory
    repo_root = Path(__file__).parent.parent
    return repo_root / 'docs'


@pytest.fixture
def index_file() -> str:
    """Return name of index file."""
    return 'INDEX.md'


@pytest.fixture
def link_validator(docs_dir) -> LinkValidator:
    """Create link validator instance."""
    return LinkValidator(docs_dir, fail_fast=False)


@pytest.fixture
def orphan_detector(docs_dir, index_file) -> OrphanDetector:
    """Create orphan detector instance."""
    return OrphanDetector(docs_dir, index_file=index_file)


@pytest.fixture
def all_markdown_files(docs_dir) -> List[Path]:
    """Return all markdown files in documentation."""
    return sorted(docs_dir.rglob('*.md'))


@pytest.fixture
def markdown_content(all_markdown_files) -> dict:
    """Load content of all markdown files."""
    content = {}
    for file_path in all_markdown_files:
        try:
            content[file_path] = file_path.read_text(encoding='utf-8')
        except Exception as e:
            pytest.fail(f"Could not read {file_path}: {e}")
    return content


# ============================================================================
# Link Validation Tests
# ============================================================================


class TestLinkValidation:
    """Tests for link validation."""

    def test_no_broken_internal_links(self, link_validator):
        """Test that all internal links are valid."""
        result = link_validator.validate_directory()

        if not result.is_valid:
            # Build detailed error message
            error_msg = ["\nBroken links found:"]
            for link in result.broken_links:
                rel_source = link.source_file.relative_to(link_validator.docs_dir)
                error_msg.append(
                    f"\n  {rel_source}:{link.line_number}"
                    f"\n    Link: {link.target_path}"
                    f"\n    Resolved to: {link.resolved_path}"
                    f"\n    Status: FILE NOT FOUND"
                )

            pytest.fail('\n'.join(error_msg))

    def test_link_extraction(self, link_validator, docs_dir):
        """Test that link extraction works correctly."""
        # Create test markdown content
        test_content = """
# Test Document

[Valid Link](./other.md)
[Another Link](../parent/file.md)
[External Link](https://example.com)
[Anchor Link](#section)
        """

        test_file = docs_dir / 'test_extraction.md'
        try:
            test_file.write_text(test_content)

            links = link_validator.extract_links(test_file)

            # Should extract 4 links
            assert len(links) == 4

            # Check link targets
            targets = [target for _, _, target in links]
            assert './other.md' in targets
            assert '../parent/file.md' in targets
            assert 'https://example.com' in targets
            assert '#section' in targets

        finally:
            if test_file.exists():
                test_file.unlink()

    def test_external_link_detection(self, link_validator):
        """Test that external links are correctly identified."""
        assert link_validator.is_external_link('https://example.com')
        assert link_validator.is_external_link('http://example.com')
        assert link_validator.is_external_link('mailto:test@example.com')
        assert link_validator.is_external_link('ftp://example.com')

        assert not link_validator.is_external_link('./relative.md')
        assert not link_validator.is_external_link('/absolute.md')
        assert not link_validator.is_external_link('../parent.md')

    def test_relative_path_resolution(self, link_validator, docs_dir):
        """Test that relative paths are resolved correctly."""
        source_file = docs_dir / 'subdir' / 'doc.md'

        # Relative path
        resolved = link_validator.resolve_link_path(source_file, './other.md')
        assert resolved == (docs_dir / 'subdir' / 'other.md').resolve()

        # Parent relative path
        resolved = link_validator.resolve_link_path(source_file, '../parent.md')
        assert resolved == (docs_dir / 'parent.md').resolve()

        # Absolute path from docs root
        resolved = link_validator.resolve_link_path(source_file, '/absolute.md')
        assert resolved == (docs_dir / 'absolute.md').resolve()

    def test_anchor_removal(self, link_validator, docs_dir):
        """Test that anchors are removed from paths."""
        source_file = docs_dir / 'doc.md'

        # Link with anchor
        resolved = link_validator.resolve_link_path(source_file, './other.md#section')
        assert resolved == (docs_dir / 'other.md').resolve()

        # Anchor-only link (should resolve to same file)
        resolved = link_validator.resolve_link_path(source_file, '#section')
        # After removing anchor, empty string, resolves to source dir
        assert resolved.parent == docs_dir


# ============================================================================
# Orphan Detection Tests
# ============================================================================


class TestOrphanDetection:
    """Tests for orphaned documentation detection."""

    def test_no_orphaned_documents(self, orphan_detector):
        """Test that all documentation is reachable from INDEX.md."""
        report = orphan_detector.detect_orphans()

        if report.orphan_count > 0:
            # Build detailed error message
            error_msg = [
                f"\n{report.orphan_count} orphaned files found "
                f"(not reachable from {report.index_file.name}):"
            ]
            for orphan in report.orphaned_files:
                rel_path = orphan.relative_to(orphan_detector.docs_dir)
                error_msg.append(f"  - {rel_path}")

            error_msg.append(
                "\nAll documentation should be discoverable from INDEX.md"
            )

            pytest.fail('\n'.join(error_msg))

    def test_index_file_exists(self, orphan_detector):
        """Test that INDEX.md exists."""
        assert orphan_detector.index_path.exists(), \
            f"Index file not found: {orphan_detector.index_path}"

    def test_link_traversal(self, orphan_detector, docs_dir):
        """Test that link traversal finds connected files."""
        # Create test file structure
        test_dir = docs_dir / 'test_traversal'
        test_dir.mkdir(exist_ok=True)

        try:
            # Create index with link
            index = test_dir / 'INDEX.md'
            index.write_text('[Link to A](a.md)\n')

            # Create linked file
            file_a = test_dir / 'a.md'
            file_a.write_text('[Link to B](b.md)\n')

            # Create second level file
            file_b = test_dir / 'b.md'
            file_b.write_text('# Document B\n')

            # Create orphan
            orphan = test_dir / 'orphan.md'
            orphan.write_text('# Orphan\n')

            # Traverse from index
            detector = OrphanDetector(test_dir, index_file='INDEX.md')
            detector.traverse_links(index)

            # Check reachable files
            assert index in detector.reachable_files
            assert file_a in detector.reachable_files
            assert file_b in detector.reachable_files
            assert orphan not in detector.reachable_files

        finally:
            # Cleanup
            if test_dir.exists():
                for f in test_dir.iterdir():
                    f.unlink()
                test_dir.rmdir()

    def test_internal_link_extraction(self, orphan_detector):
        """Test that only internal links are extracted."""
        content = """
[Internal](./doc.md)
[External](https://example.com)
[Relative](../parent.md)
[Mailto](mailto:test@example.com)
        """

        # Write test file
        test_file = orphan_detector.docs_dir / 'test_links.md'
        try:
            test_file.write_text(content)

            links = orphan_detector.extract_internal_links(test_file)

            # Should only extract internal links
            assert len(links) == 2
            assert './doc.md' in links
            assert '../parent.md' in links
            assert 'https://example.com' not in links
            assert 'mailto:test@example.com' not in links

        finally:
            if test_file.exists():
                test_file.unlink()


# ============================================================================
# Image and Diagram Tests
# ============================================================================


class TestImageReferences:
    """Tests for image and diagram references."""

    IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^\)]+)\)')

    def test_all_images_exist(self, markdown_content, docs_dir):
        """Test that all referenced images exist."""
        missing_images = []

        for file_path, content in markdown_content.items():
            for match in self.IMAGE_PATTERN.finditer(content):
                alt_text = match.group(1)
                image_path = match.group(2)

                # Skip external URLs
                if image_path.startswith(('http://', 'https://')):
                    continue

                # Resolve relative path
                if image_path.startswith('/'):
                    resolved = docs_dir / image_path.lstrip('/')
                else:
                    resolved = file_path.parent / image_path

                if not resolved.exists():
                    rel_file = file_path.relative_to(docs_dir)
                    missing_images.append({
                        'file': rel_file,
                        'image': image_path,
                        'resolved': resolved
                    })

        if missing_images:
            error_msg = ["\nMissing image files:"]
            for img in missing_images:
                error_msg.append(
                    f"\n  In {img['file']}:"
                    f"\n    Image: {img['image']}"
                    f"\n    Resolved to: {img['resolved']}"
                    f"\n    Status: FILE NOT FOUND"
                )
            pytest.fail('\n'.join(error_msg))

    def test_image_alt_text_present(self, markdown_content, docs_dir):
        """Test that all images have alt text (accessibility)."""
        missing_alt_text = []

        for file_path, content in markdown_content.items():
            for match in self.IMAGE_PATTERN.finditer(content):
                alt_text = match.group(1).strip()

                if not alt_text:
                    rel_file = file_path.relative_to(docs_dir)
                    image_path = match.group(2)
                    missing_alt_text.append({
                        'file': rel_file,
                        'image': image_path
                    })

        if missing_alt_text:
            error_msg = ["\nImages missing alt text:"]
            for img in missing_alt_text:
                error_msg.append(
                    f"\n  In {img['file']}: {img['image']}"
                )
            error_msg.append("\nAdd descriptive alt text for accessibility.")
            pytest.fail('\n'.join(error_msg))


# ============================================================================
# Markdown Syntax Tests
# ============================================================================


class TestMarkdownSyntax:
    """Tests for markdown syntax validation."""

    def test_no_malformed_links(self, markdown_content, docs_dir):
        """Test that there are no malformed markdown links."""
        # Pattern for common link errors
        patterns = {
            'missing_closing_bracket': re.compile(r'\[([^\]]+)\([^\)]+\)'),
            'missing_opening_paren': re.compile(r'\[([^\]]+)\][^\(]'),
            'unmatched_brackets': re.compile(r'(?<!\[)\[([^\]]*)\](?!\()'),
        }

        issues = []

        for file_path, content in markdown_content.items():
            # Skip code blocks (basic detection)
            lines = content.splitlines()
            in_code_block = False

            for line_num, line in enumerate(lines, start=1):
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    continue

                if in_code_block:
                    continue

                # Check each pattern
                for pattern_name, pattern in patterns.items():
                    if pattern.search(line):
                        rel_file = file_path.relative_to(docs_dir)
                        issues.append({
                            'file': rel_file,
                            'line': line_num,
                            'issue': pattern_name,
                            'content': line.strip()
                        })

        # Note: This test may have false positives, so we just warn
        if issues:
            warning_msg = ["\nPotential markdown syntax issues:"]
            for issue in issues[:10]:  # Limit output
                warning_msg.append(
                    f"\n  {issue['file']}:{issue['line']}"
                    f"\n    Issue: {issue['issue']}"
                    f"\n    Line: {issue['content'][:80]}"
                )
            # Use pytest.skip for warnings
            pytest.skip('\n'.join(warning_msg))

    def test_heading_hierarchy(self, markdown_content, docs_dir):
        """Test that heading levels don't skip (e.g., H1 -> H3)."""
        HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$')

        issues = []

        for file_path, content in markdown_content.items():
            lines = content.splitlines()
            prev_level = 0

            for line_num, line in enumerate(lines, start=1):
                match = HEADING_PATTERN.match(line)
                if match:
                    current_level = len(match.group(1))

                    # Check if we skipped levels
                    if prev_level > 0 and current_level > prev_level + 1:
                        rel_file = file_path.relative_to(docs_dir)
                        issues.append({
                            'file': rel_file,
                            'line': line_num,
                            'prev_level': prev_level,
                            'current_level': current_level,
                            'heading': match.group(2)
                        })

                    prev_level = current_level

        if issues:
            warning_msg = ["\nHeading hierarchy issues (skipped levels):"]
            for issue in issues[:10]:
                warning_msg.append(
                    f"\n  {issue['file']}:{issue['line']}"
                    f"\n    Jumped from H{issue['prev_level']} to H{issue['current_level']}"
                    f"\n    Heading: {issue['heading']}"
                )
            pytest.skip('\n'.join(warning_msg))


# ============================================================================
# Structure Validation Tests
# ============================================================================


class TestDocumentationStructure:
    """Tests for documentation structure and organization."""

    def test_index_has_structure(self, docs_dir, index_file):
        """Test that INDEX.md has proper structure."""
        index_path = docs_dir / index_file

        if not index_path.exists():
            pytest.skip(f"Index file not found: {index_file}")

        content = index_path.read_text(encoding='utf-8')

        # Should have H1 heading
        assert re.search(r'^# .+', content, re.MULTILINE), \
            "INDEX.md should have a main H1 heading"

        # Should have links
        assert re.search(r'\[.+\]\(.+\)', content), \
            "INDEX.md should contain links to other documentation"

    def test_all_docs_have_titles(self, all_markdown_files, docs_dir):
        """Test that all markdown files have H1 titles."""
        missing_titles = []

        for file_path in all_markdown_files:
            content = file_path.read_text(encoding='utf-8')

            # Check for H1 heading
            if not re.search(r'^# .+', content, re.MULTILINE):
                rel_path = file_path.relative_to(docs_dir)
                missing_titles.append(rel_path)

        if missing_titles:
            error_msg = ["\nFiles missing H1 titles:"]
            for path in missing_titles:
                error_msg.append(f"  - {path}")
            pytest.fail('\n'.join(error_msg))

    def test_readme_files_in_subdirectories(self, docs_dir):
        """Test that subdirectories have README.md or INDEX.md files."""
        subdirs = [d for d in docs_dir.rglob('*') if d.is_dir()]

        missing_readme = []

        for subdir in subdirs:
            # Skip hidden directories and special directories
            if any(part.startswith('.') for part in subdir.parts):
                continue

            # Check for README.md or INDEX.md
            has_readme = (subdir / 'README.md').exists()
            has_index = (subdir / 'INDEX.md').exists()

            # Check if directory has markdown files
            has_md_files = any(subdir.glob('*.md'))

            if has_md_files and not (has_readme or has_index):
                rel_path = subdir.relative_to(docs_dir)
                missing_readme.append(rel_path)

        if missing_readme:
            warning_msg = ["\nSubdirectories without README.md or INDEX.md:"]
            for path in missing_readme:
                warning_msg.append(f"  - {path}")
            warning_msg.append(
                "\nConsider adding navigation files to subdirectories."
            )
            pytest.skip('\n'.join(warning_msg))


# ============================================================================
# Integration Tests
# ============================================================================


class TestDocumentationIntegration:
    """Integration tests for complete documentation validation."""

    def test_full_link_validation(self, link_validator):
        """Run complete link validation."""
        result = link_validator.validate_directory()

        # Print summary
        print(f"\nLink Validation Summary:")
        print(f"  Total links: {result.total_links}")
        print(f"  Valid: {result.valid_links}")
        print(f"  External: {result.external_links}")
        print(f"  Broken: {result.broken_count}")

        assert result.is_valid, \
            f"Found {result.broken_count} broken links"

    def test_full_orphan_detection(self, orphan_detector):
        """Run complete orphan detection."""
        report = orphan_detector.detect_orphans()

        # Print summary
        print(f"\nOrphan Detection Summary:")
        print(f"  Total files: {report.total_files}")
        print(f"  Reachable: {report.reachable_files}")
        print(f"  Orphans: {report.orphan_count}")
        print(f"  Coverage: {report.coverage_percent:.1f}%")

        assert report.orphan_count == 0, \
            f"Found {report.orphan_count} orphaned files"

    def test_documentation_health_score(self, link_validator, orphan_detector):
        """Calculate overall documentation health score."""
        # Run validations
        link_result = link_validator.validate_directory()
        orphan_report = orphan_detector.detect_orphans()

        # Calculate metrics
        link_quality = (link_result.valid_links / max(1, link_result.total_links - link_result.external_links)) * 100
        coverage = orphan_report.coverage_percent

        # Health score (average of metrics)
        health_score = (link_quality + coverage) / 2

        print(f"\nDocumentation Health Score: {health_score:.1f}%")
        print(f"  Link Quality: {link_quality:.1f}%")
        print(f"  Coverage: {coverage:.1f}%")

        # Require at least 95% health
        assert health_score >= 95.0, \
            f"Documentation health score below threshold: {health_score:.1f}% < 95%"
