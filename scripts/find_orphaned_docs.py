#!/usr/bin/env python3
"""
Orphaned documentation detection script.

Finds documentation files that are not reachable from INDEX.md through
link traversal. All documentation should be discoverable from the index.

Supports --fix mode to suggest additions to INDEX.md.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set


@dataclass
class OrphanReport:
    """Report of orphaned documentation analysis."""

    total_files: int
    reachable_files: int
    orphaned_files: List[Path]
    index_file: Path

    @property
    def orphan_count(self) -> int:
        """Count of orphaned files."""
        return len(self.orphaned_files)

    @property
    def coverage_percent(self) -> float:
        """Percentage of files reachable from index."""
        if self.total_files == 0:
            return 100.0
        return (self.reachable_files / self.total_files) * 100


class OrphanDetector:
    """Detects orphaned documentation files."""

    # Markdown link patterns
    MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")
    ANCHOR_PATTERN = re.compile(r"#.*$")

    # External link patterns
    EXTERNAL_PROTOCOLS = ("http://", "https://", "mailto:", "ftp://")

    def __init__(self, docs_dir: Path, index_file: str = "INDEX.md"):
        """
        Initialize orphan detector.

        Args:
            docs_dir: Root documentation directory
            index_file: Name of index file (default: INDEX.md)
        """
        self.docs_dir = docs_dir.resolve()
        self.index_path = self.docs_dir / index_file
        self.reachable_files: Set[Path] = set()
        self.visited_files: Set[Path] = set()

    def extract_internal_links(self, file_path: Path) -> List[str]:
        """
        Extract internal links from markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            List of internal link targets
        """
        links = []

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
            return links

        for match in self.MARKDOWN_LINK_PATTERN.finditer(content):
            target = match.group(2)

            # Skip external links
            if any(target.startswith(proto) for proto in self.EXTERNAL_PROTOCOLS):
                continue

            # Remove anchor
            target_without_anchor = self.ANCHOR_PATTERN.sub("", target)

            if target_without_anchor:  # Skip empty links (anchor-only)
                links.append(target_without_anchor)

        return links

    def resolve_link(self, source_file: Path, target: str) -> Path:
        """
        Resolve relative link to absolute path.

        Args:
            source_file: Source file containing link
            target: Target path from link

        Returns:
            Resolved absolute path
        """
        if target.startswith("/"):
            # Absolute from docs root
            return self.docs_dir / target.lstrip("/")
        else:
            # Relative from source directory
            source_dir = source_file.parent
            return (source_dir / target).resolve()

    def traverse_links(self, start_file: Path) -> None:
        """
        Recursively traverse links from start file.

        Args:
            start_file: File to start traversal from
        """
        # Normalize path
        start_file = start_file.resolve()

        # Skip if already visited
        if start_file in self.visited_files:
            return

        # Mark as visited
        self.visited_files.add(start_file)

        # Skip if file doesn't exist
        if not start_file.exists():
            return

        # Mark as reachable
        self.reachable_files.add(start_file)

        # Extract and follow links
        links = self.extract_internal_links(start_file)
        for link in links:
            resolved = self.resolve_link(start_file, link)

            # Only traverse markdown files within docs dir
            if resolved.suffix == ".md" and resolved.is_relative_to(self.docs_dir):
                self.traverse_links(resolved)

    def find_all_markdown_files(self) -> Set[Path]:
        """
        Find all markdown files in docs directory.

        Returns:
            Set of all markdown file paths
        """
        return set(self.docs_dir.rglob("*.md"))

    def detect_orphans(self) -> OrphanReport:
        """
        Detect orphaned documentation files.

        Returns:
            OrphanReport with analysis results
        """
        # Check if index exists
        if not self.index_path.exists():
            print(f"Error: Index file not found: {self.index_path}", file=sys.stderr)
            sys.exit(1)

        # Traverse from index
        self.traverse_links(self.index_path)

        # Find all markdown files
        all_files = self.find_all_markdown_files()

        # Identify orphans
        orphaned = sorted(all_files - self.reachable_files)

        return OrphanReport(
            total_files=len(all_files),
            reachable_files=len(self.reachable_files),
            orphaned_files=orphaned,
            index_file=self.index_path,
        )

    def format_report(self, report: OrphanReport, suggest_fix: bool = False) -> str:
        """
        Format orphan detection report.

        Args:
            report: Orphan report
            suggest_fix: Include fix suggestions

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("Orphaned Documentation Detection Report")
        lines.append("=" * 70)
        lines.append("")
        lines.append(
            f"Index file:        {report.index_file.relative_to(self.docs_dir)}"
        )
        lines.append(f"Total MD files:    {report.total_files}")
        lines.append(f"Reachable files:   {report.reachable_files}")
        lines.append(f"Orphaned files:    {report.orphan_count}")
        lines.append(f"Coverage:          {report.coverage_percent:.1f}%")
        lines.append("")

        if report.orphaned_files:
            lines.append("ORPHANED FILES (not reachable from INDEX.md):")
            lines.append("-" * 70)

            for orphan in report.orphaned_files:
                rel_path = orphan.relative_to(self.docs_dir)
                lines.append(f"  - {rel_path}")

            if suggest_fix:
                lines.append("")
                lines.append("SUGGESTED FIXES:")
                lines.append("-" * 70)
                lines.append("Add these files to INDEX.md or link from existing docs:")
                lines.append("")

                for orphan in report.orphaned_files:
                    rel_path = orphan.relative_to(self.docs_dir)
                    # Try to extract title from file
                    title = (
                        self._extract_title(orphan)
                        or rel_path.stem.replace("_", " ").title()
                    )
                    lines.append(f"- [{title}]({rel_path})")
        else:
            lines.append("✓ All documentation files are reachable from INDEX.md!")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def _extract_title(self, file_path: Path) -> str:
        """
        Extract title from markdown file (first H1 heading).

        Args:
            file_path: Path to markdown file

        Returns:
            Title or empty string if not found
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
        except Exception:
            pass
        return ""


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Find orphaned documentation files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find orphans in docs directory
  %(prog)s

  # Use custom index file
  %(prog)s --index README.md

  # Suggest fixes for INDEX.md
  %(prog)s --suggest-fix

  # Exit with error if orphans found
  %(prog)s --strict
        """,
    )

    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs"),
        help="Documentation directory (default: docs)",
    )

    parser.add_argument(
        "--index",
        type=str,
        default="INDEX.md",
        help="Index file name (default: INDEX.md)",
    )

    parser.add_argument(
        "--suggest-fix", action="store_true", help="Suggest additions to INDEX.md"
    )

    parser.add_argument(
        "--strict", action="store_true", help="Exit with error code if orphans found"
    )

    parser.add_argument(
        "--quiet", action="store_true", help="Only show summary and orphans"
    )

    args = parser.parse_args()

    # Resolve docs directory
    docs_dir = args.docs_dir.resolve()

    if not docs_dir.exists():
        print(f"Error: Documentation directory not found: {docs_dir}", file=sys.stderr)
        return 1

    if not docs_dir.is_dir():
        print(f"Error: Not a directory: {docs_dir}", file=sys.stderr)
        return 1

    # Run detection
    if not args.quiet:
        print(f"Analyzing documentation in: {docs_dir}")
        print()

    detector = OrphanDetector(docs_dir, index_file=args.index)
    report = detector.detect_orphans()

    # Print report
    print(detector.format_report(report, suggest_fix=args.suggest_fix))

    # Exit code
    if args.strict and report.orphan_count > 0:
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
