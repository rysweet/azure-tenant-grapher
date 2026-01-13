#!/usr/bin/env python3
"""
Validate documentation links to ensure no broken references.

Usage:
    python scripts/validate_docs_links.py
    python scripts/validate_docs_links.py --fix
"""

import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


class LinkValidator:
    """Validates and optionally fixes broken links in markdown documentation."""

    def __init__(self, docs_dir: Path, fix: bool = False):
        self.docs_dir = docs_dir
        self.fix = fix
        self.broken_links: List[Tuple[Path, str, str]] = []
        self.fixed_links: Dict[str, str] = {}

    def find_markdown_files(self) -> List[Path]:
        """Find all markdown files in docs directory."""
        return list(self.docs_dir.rglob("*.md"))

    def extract_links(self, content: str) -> List[str]:
        """Extract all markdown links from content."""
        # Match [text](link) pattern
        link_pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
        return [match[1] for match in re.findall(link_pattern, content)]

    def validate_link(self, source_file: Path, link: str) -> bool:
        """Validate if a link target exists."""
        # Skip external links
        if link.startswith(("http://", "https://", "mailto:", "#")):
            return True

        # Handle relative links
        if link.startswith("../") or link.startswith("./"):
            # Explicit relative path
            target_path = (source_file.parent / link).resolve()
        else:
            # Implicit relative path - try relative to source file first
            target_path = (source_file.parent / link).resolve()
            # If not found, try relative to docs/ directory as fallback
            if not target_path.exists():
                target_path = (self.docs_dir / link).resolve()

        # Remove anchor if present
        if "#" in str(target_path):
            target_path = Path(str(target_path).split("#")[0])

        return target_path.exists()

    def suggest_fix(self, source_file: Path, broken_link: str) -> str:
        """Suggest a fix for a broken link."""
        # Extract filename from link
        link_parts = broken_link.split("/")
        filename = link_parts[-1].split("#")[0]

        # Search for file in docs directory
        matches = list(self.docs_dir.rglob(filename))

        if not matches:
            return None

        # Calculate relative path from source file to target
        source_dir = source_file.parent
        target_file = matches[0]

        try:
            relative_path = target_file.relative_to(source_dir)
            return str(relative_path)
        except ValueError:
            # Files not in relative path, use absolute from docs/
            try:
                relative_path = target_file.relative_to(self.docs_dir)
                return str(relative_path)
            except ValueError:
                return None

    def validate_all(self) -> int:
        """Validate all documentation links."""
        markdown_files = self.find_markdown_files()

        print(str(f"Validating links in {len(markdown_files)} markdown files..."))
        print()

        for md_file in markdown_files:
            content = md_file.read_text()
            links = self.extract_links(content)

            for link in links:
                if not self.validate_link(md_file, link):
                    self.broken_links.append((md_file, link, content))

                    if self.fix:
                        suggestion = self.suggest_fix(md_file, link)
                        if suggestion:
                            self.fixed_links[link] = suggestion

        return len(self.broken_links)

    def report(self):
        """Print validation report."""
        if not self.broken_links:
            print("✅ All links are valid!")
            return

        print(str(f"❌ Found {len(self.broken_links)} broken links:\n"))

        # Group by file
        links_by_file = defaultdict(list)
        for file_path, link, _ in self.broken_links:
            links_by_file[file_path].append(link)

        for file_path, links in sorted(links_by_file.items()):
            rel_path = file_path.relative_to(self.docs_dir.parent)
            print(str(f"📄 {rel_path}"))
            for link in links:
                print(str(f"   - {link}"))
                if link in self.fixed_links:
                    print(str(f"     → Suggested fix: {self.fixed_links[link]}"))
            print()

    def apply_fixes(self):
        """Apply suggested fixes to files."""
        if not self.fix or not self.fixed_links:
            return

        files_to_fix = defaultdict(list)
        for file_path, link, _content in self.broken_links:
            if link in self.fixed_links:
                files_to_fix[file_path].append((link, self.fixed_links[link]))

        print(str(f"\n🔧 Applying fixes to {len(files_to_fix)} files...\n"))

        for file_path, fixes in files_to_fix.items():
            content = file_path.read_text()
            for old_link, new_link in fixes:
                # Replace link while preserving markdown format
                content = content.replace(f"]({old_link})", f"]({new_link})")

            file_path.write_text(content)
            rel_path = file_path.relative_to(self.docs_dir.parent)
            print(str(f"✅ Fixed {len(fixes)} links in {rel_path}"))


def main():
    parser = argparse.ArgumentParser(description="Validate documentation links")
    parser.add_argument(
        "--fix", action="store_true", help="Attempt to fix broken links automatically"
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs"),
        help="Documentation directory (default: docs)",
    )
    args = parser.parse_args()

    docs_dir = args.docs_dir.resolve()
    if not docs_dir.exists():
        print(str(f"❌ Documentation directory not found: {docs_dir}"))
        return 1

    validator = LinkValidator(docs_dir, fix=args.fix)
    num_broken = validator.validate_all()
    validator.report()

    if args.fix:
        validator.apply_fixes()

    return 1 if num_broken > 0 else 0


if __name__ == "__main__":
    exit(main())
