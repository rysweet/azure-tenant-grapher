#!/usr/bin/env python3
"""
Technical Debt Analyzer
Comprehensive detection and reporting of technical debt patterns
"""

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Severity(Enum):
    """Issue severity levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(Enum):
    """Technical debt categories"""

    STUB = "stub"
    TODO = "todo"
    EXCEPTION = "swallowed_exception"
    FAKE = "fake_api"
    UNIMPLEMENTED = "unimplemented"


@dataclass
class Issue:
    """Represents a single technical debt issue"""

    id: str
    category: Category
    severity: Severity
    pattern_id: str
    file_path: str
    line_number: int
    column: int
    code_snippet: str
    context: str
    recommendation: str
    is_production: bool
    estimated_effort_hours: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "pattern_id": self.pattern_id,
            "file": self.file_path,
            "line": self.line_number,
            "column": self.column,
            "code_snippet": self.code_snippet,
            "context": self.context,
            "recommendation": self.recommendation,
            "is_production": self.is_production,
            "estimated_effort_hours": self.estimated_effort_hours,
        }


@dataclass
class ScanResult:
    """Complete scan results"""

    scan_metadata: Dict[str, Any] = field(default_factory=dict)
    issues: List[Issue] = field(default_factory=list)
    false_positives: List[Dict[str, Any]] = field(default_factory=list)
    acceptable_exceptions: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "scan_metadata": self.scan_metadata,
            "issues": [issue.to_dict() for issue in self.issues],
            "false_positives": self.false_positives,
            "acceptable_exceptions": self.acceptable_exceptions,
            "summary": self.summary,
        }


class TechnicalDebtAnalyzer:
    """Main analyzer class"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues: List[Issue] = []
        self.issue_counter = 0

        # Define search patterns
        self.patterns = self._load_patterns()

        # Test directories to exclude
        self.test_exclusions = [
            "tests/",
            "test_*.py",
            "*_test.py",
            "conftest.py",
            "*.test.ts",
            "*.test.tsx",
            "*.spec.ts",
            "__tests__/",
            "examples/",
            "demos/",
        ]

    def _load_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load search patterns organized by category"""
        return {
            "python_stubs": [
                {
                    "id": "PY-STUB-001",
                    "pattern": r"def\s+\w+\([^)]*\):\s*\n\s*pass",
                    "severity": Severity.HIGH,
                    "description": "Function with pass-only body",
                    "recommendation": "Implement function logic or mark as abstract",
                    "effort": 2.0,
                },
                {
                    "id": "PY-STUB-002",
                    "pattern": r"raise\s+NotImplementedError",
                    "severity": Severity.HIGH,
                    "description": "NotImplementedError in production code",
                    "recommendation": "Implement missing functionality",
                    "effort": 4.0,
                },
                {
                    "id": "PY-STUB-004",
                    "pattern": r"^\s*\.\.\.\s*$",
                    "severity": Severity.HIGH,
                    "description": "Ellipsis stub implementation",
                    "recommendation": "Implement or remove stub",
                    "effort": 2.0,
                },
            ],
            "typescript_stubs": [
                {
                    "id": "TS-STUB-001",
                    "pattern": r"function\s+\w+\([^)]*\)\s*\{\s*\}",
                    "severity": Severity.HIGH,
                    "description": "Empty function implementation",
                    "recommendation": "Implement function body",
                    "effort": 2.0,
                },
                {
                    "id": "TS-STUB-002",
                    "pattern": r"=>\s*undefined",
                    "severity": Severity.MEDIUM,
                    "description": "Arrow function returning undefined",
                    "recommendation": "Implement proper return value",
                    "effort": 1.0,
                },
            ],
            "todos": [
                {
                    "id": "TODO-001",
                    "pattern": r"TODO:",
                    "severity": Severity.HIGH,
                    "description": "TODO comment",
                    "recommendation": "Convert to GitHub issue or implement",
                    "effort": 0.5,
                },
                {
                    "id": "TODO-002",
                    "pattern": r"FIXME:",
                    "severity": Severity.CRITICAL,
                    "description": "FIXME comment indicating broken code",
                    "recommendation": "Fix immediately",
                    "effort": 2.0,
                },
                {
                    "id": "TODO-003",
                    "pattern": r"HACK:",
                    "severity": Severity.HIGH,
                    "description": "HACK comment",
                    "recommendation": "Replace with proper implementation",
                    "effort": 3.0,
                },
                {
                    "id": "TODO-004",
                    "pattern": r"XXX:",
                    "severity": Severity.HIGH,
                    "description": "XXX warning comment",
                    "recommendation": "Address issue or convert to tracked item",
                    "effort": 1.0,
                },
                {
                    "id": "TODO-005",
                    "pattern": r"(TEMPORARY|TEMP):",
                    "severity": Severity.CRITICAL,
                    "description": "Temporary code in production",
                    "recommendation": "Remove or make permanent with proper implementation",
                    "effort": 4.0,
                },
            ],
            "python_exceptions": [
                {
                    "id": "PY-EXCEPT-001",
                    "pattern": r"except[^:]*:\s*\n\s*pass",
                    "severity": Severity.CRITICAL,
                    "description": "Exception swallowed with pass",
                    "recommendation": "Add logging and proper error handling",
                    "effort": 1.0,
                },
                {
                    "id": "PY-EXCEPT-002",
                    "pattern": r"^\s*except\s*:",
                    "severity": Severity.CRITICAL,
                    "description": "Bare except clause",
                    "recommendation": "Specify exception type",
                    "effort": 0.5,
                },
                {
                    "id": "PY-EXCEPT-004",
                    "pattern": r"except[^:]*:\s*\n\s*#.*TODO",
                    "severity": Severity.CRITICAL,
                    "description": "Exception handler with TODO",
                    "recommendation": "Implement error handling",
                    "effort": 2.0,
                },
            ],
            "typescript_exceptions": [
                {
                    "id": "TS-EXCEPT-001",
                    "pattern": r"catch\s*\([^)]*\)\s*\{\s*\}",
                    "severity": Severity.CRITICAL,
                    "description": "Empty catch block",
                    "recommendation": "Add error logging and handling",
                    "effort": 1.0,
                },
                {
                    "id": "TS-EXCEPT-003",
                    "pattern": r"catch\s*\([^)]*\)\s*\{[^}]*TODO",
                    "severity": Severity.CRITICAL,
                    "description": "Catch block with TODO",
                    "recommendation": "Implement error handling",
                    "effort": 2.0,
                },
            ],
            "fakes": [
                {
                    "id": "PY-FAKE-001",
                    "pattern": r"@(mock\.|patch)",
                    "severity": Severity.CRITICAL,
                    "description": "Mock decorator in production code",
                    "recommendation": "Remove mocking from production",
                    "effort": 4.0,
                },
                {
                    "id": "PY-FAKE-002",
                    "pattern": r"(MOCK_|FAKE_|DUMMY_|TEST_DATA)",
                    "severity": Severity.HIGH,
                    "description": "Hardcoded mock/fake data",
                    "recommendation": "Replace with real data or configuration",
                    "effort": 2.0,
                },
                {
                    "id": "PY-FAKE-003",
                    "pattern": r"def\s+(fake|mock|stub)_\w+",
                    "severity": Severity.HIGH,
                    "description": "Function with fake/mock name",
                    "recommendation": "Implement real functionality",
                    "effort": 4.0,
                },
            ],
        }

    def _run_ripgrep(
        self,
        pattern: str,
        file_types: Optional[List[str]] = None,
        paths: Optional[List[Path]] = None,
        multiline: bool = False,
        case_insensitive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Run ripgrep and parse results

        Returns list of matches with file, line, column, and text
        """
        cmd = ["rg", "--json"]

        if multiline:
            cmd.extend(["--multiline", "--multiline-dotall"])

        if case_insensitive:
            cmd.append("-i")

        if file_types:
            for ft in file_types:
                cmd.extend(["--type", ft])

        # Add exclusions
        for exclusion in self.test_exclusions:
            cmd.extend(["--glob", f"!{exclusion}"])

        cmd.append(pattern)

        if paths:
            cmd.extend([str(p) for p in paths])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.project_root
            )

            matches = []
            for line in result.stdout.splitlines():
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data.get("data", {})
                        matches.append(
                            {
                                "file": match_data.get("path", {}).get("text", ""),
                                "line": match_data.get("line_number", 0),
                                "column": match_data.get("submatches", [{}])[0].get(
                                    "start", 0
                                ),
                                "text": match_data.get("lines", {})
                                .get("text", "")
                                .strip(),
                            }
                        )
                except json.JSONDecodeError:
                    continue

            return matches

        except subprocess.CalledProcessError:
            return []
        except FileNotFoundError:
            print("Error: ripgrep (rg) not found. Install with: brew install ripgrep")
            return []

    def _is_production_file(self, file_path: str) -> bool:
        """Determine if file is production code (not test/example)"""
        test_indicators = [
            "/tests/",
            "/test/",
            "test_",
            "_test.",
            ".test.",
            ".spec.",
            "/examples/",
            "/demos/",
            "/fixtures/",
            "conftest.py",
        ]
        return not any(indicator in file_path for indicator in test_indicators)

    def _create_issue(
        self, match: Dict[str, Any], pattern: Dict[str, Any], category: Category
    ) -> Issue:
        """Create an Issue object from a match and pattern"""
        self.issue_counter += 1

        return Issue(
            id=f"{category.value.upper()}-{self.issue_counter:04d}",
            category=category,
            severity=pattern["severity"],
            pattern_id=pattern["id"],
            file_path=match["file"],
            line_number=match["line"],
            column=match["column"],
            code_snippet=match["text"],
            context=pattern["description"],
            recommendation=pattern["recommendation"],
            is_production=self._is_production_file(match["file"]),
            estimated_effort_hours=pattern["effort"],
        )

    def scan_python_stubs(self):
        """Scan for Python stub implementations"""
        for pattern in self.patterns["python_stubs"]:
            matches = self._run_ripgrep(
                pattern=pattern["pattern"],
                file_types=["py"],
                paths=[self.project_root / "src"],
                multiline="\\n" in pattern["pattern"],
            )

            for match in matches:
                if self._is_production_file(match["file"]):
                    issue = self._create_issue(match, pattern, Category.STUB)
                    self.issues.append(issue)

    def scan_typescript_stubs(self):
        """Scan for TypeScript stub implementations"""
        for pattern in self.patterns["typescript_stubs"]:
            matches = self._run_ripgrep(
                pattern=pattern["pattern"],
                file_types=["ts"],
                paths=[self.project_root / "spa"],
                multiline="\\{" in pattern["pattern"],
            )

            for match in matches:
                if self._is_production_file(match["file"]):
                    issue = self._create_issue(match, pattern, Category.STUB)
                    self.issues.append(issue)

    def scan_todos(self):
        """Scan for TODO comments"""
        for pattern in self.patterns["todos"]:
            matches = self._run_ripgrep(
                pattern=pattern["pattern"],
                file_types=["py", "ts", "js"],
                paths=[self.project_root / "src", self.project_root / "spa"],
                case_insensitive=True,
            )

            for match in matches:
                issue = self._create_issue(match, pattern, Category.TODO)
                self.issues.append(issue)

    def scan_python_exceptions(self):
        """Scan for swallowed exceptions in Python"""
        for pattern in self.patterns["python_exceptions"]:
            matches = self._run_ripgrep(
                pattern=pattern["pattern"],
                file_types=["py"],
                paths=[self.project_root / "src"],
                multiline="\\n" in pattern["pattern"],
            )

            for match in matches:
                if self._is_production_file(match["file"]):
                    issue = self._create_issue(match, pattern, Category.EXCEPTION)
                    self.issues.append(issue)

    def scan_typescript_exceptions(self):
        """Scan for swallowed exceptions in TypeScript"""
        for pattern in self.patterns["typescript_exceptions"]:
            matches = self._run_ripgrep(
                pattern=pattern["pattern"],
                file_types=["ts"],
                paths=[self.project_root / "spa"],
                multiline=True,
            )

            for match in matches:
                if self._is_production_file(match["file"]):
                    issue = self._create_issue(match, pattern, Category.EXCEPTION)
                    self.issues.append(issue)

    def scan_fakes(self):
        """Scan for fake/mock APIs in production"""
        for pattern in self.patterns["fakes"]:
            matches = self._run_ripgrep(
                pattern=pattern["pattern"],
                file_types=["py"],
                paths=[self.project_root / "src"],
            )

            for match in matches:
                if self._is_production_file(match["file"]):
                    issue = self._create_issue(match, pattern, Category.FAKE)
                    self.issues.append(issue)

    def run_full_scan(self) -> ScanResult:
        """Execute complete technical debt scan"""
        print("Starting technical debt scan...")

        print("  Scanning Python stubs...")
        self.scan_python_stubs()

        print("  Scanning TypeScript stubs...")
        self.scan_typescript_stubs()

        print("  Scanning TODO comments...")
        self.scan_todos()

        print("  Scanning Python exceptions...")
        self.scan_python_exceptions()

        print("  Scanning TypeScript exceptions...")
        self.scan_typescript_exceptions()

        print("  Scanning for fakes/mocks...")
        self.scan_fakes()

        # Build summary
        summary = self._build_summary()

        # Get metadata
        metadata = self._get_scan_metadata()

        result = ScanResult(scan_metadata=metadata, issues=self.issues, summary=summary)

        print(str(f"\nScan complete. Found {len(self.issues)} issues."))
        return result

    def _build_summary(self) -> Dict[str, Any]:
        """Build summary statistics"""
        total = len(self.issues)

        by_severity = {
            "critical": len(
                [i for i in self.issues if i.severity == Severity.CRITICAL]
            ),
            "high": len([i for i in self.issues if i.severity == Severity.HIGH]),
            "medium": len([i for i in self.issues if i.severity == Severity.MEDIUM]),
            "low": len([i for i in self.issues if i.severity == Severity.LOW]),
        }

        by_category = {
            "stubs": len([i for i in self.issues if i.category == Category.STUB]),
            "todos": len([i for i in self.issues if i.category == Category.TODO]),
            "swallowed_exceptions": len(
                [i for i in self.issues if i.category == Category.EXCEPTION]
            ),
            "fake_apis": len([i for i in self.issues if i.category == Category.FAKE]),
            "unimplemented": len(
                [i for i in self.issues if i.category == Category.UNIMPLEMENTED]
            ),
        }

        production_issues = len([i for i in self.issues if i.is_production])
        total_effort = sum(i.estimated_effort_hours for i in self.issues)

        return {
            "total_issues": total,
            "production_issues": production_issues,
            "test_issues": total - production_issues,
            "by_severity": by_severity,
            "by_category": by_category,
            "estimated_total_effort_hours": round(total_effort, 1),
        }

    def _get_scan_metadata(self) -> Dict[str, Any]:
        """Get scan metadata including git info"""
        metadata = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "scanner_version": "1.0.0",
            "codebase_root": str(self.project_root),
        }

        try:
            # Get git info
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            ).stdout.strip()

            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            ).stdout.strip()

            metadata["commit_sha"] = commit
            metadata["branch"] = branch

        except (subprocess.CalledProcessError, FileNotFoundError):
            metadata["commit_sha"] = "N/A"
            metadata["branch"] = "N/A"

        return metadata


def main():
    """Main entry point"""
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)

    # Create analyzer and run scan
    analyzer = TechnicalDebtAnalyzer(project_root)
    result = analyzer.run_full_scan()

    # Generate output files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON output
    json_file = output_dir / f"technical_debt_detailed_{timestamp}.json"
    with open(json_file, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    print(str(f"\nJSON report: {json_file}"))

    # Summary output
    summary_file = output_dir / "technical_debt_summary.txt"
    with open(summary_file, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("TECHNICAL DEBT SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Scan Date: {result.scan_metadata['timestamp']}\n")
        f.write(f"Branch: {result.scan_metadata['branch']}\n")
        f.write(f"Commit: {result.scan_metadata['commit_sha']}\n\n")

        f.write("OVERALL SUMMARY\n")
        f.write("-" * 60 + "\n")
        f.write(f"Total Issues:       {result.summary['total_issues']}\n")
        f.write(f"Production Issues:  {result.summary['production_issues']}\n")
        f.write(f"Test Issues:        {result.summary['test_issues']}\n")
        f.write(
            f"Estimated Effort:   {result.summary['estimated_total_effort_hours']} hours\n\n"
        )

        f.write("BY SEVERITY\n")
        f.write("-" * 60 + "\n")
        for severity, count in result.summary["by_severity"].items():
            f.write(f"{severity.upper():12} {count:3d}\n")

        f.write("\nBY CATEGORY\n")
        f.write("-" * 60 + "\n")
        for category, count in result.summary["by_category"].items():
            f.write(f"{category:25} {count:3d}\n")

        if result.summary["by_severity"]["critical"] > 0:
            f.write("\n" + "!" * 60 + "\n")
            f.write(
                f"WARNING: {result.summary['by_severity']['critical']} CRITICAL issues found!\n"
            )
            f.write("!" * 60 + "\n")

    print(str(f"Summary report: {summary_file}"))

    # Print summary to console
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total Issues: {result.summary['total_issues']}")
    print(f"  Critical:   {result.summary['by_severity']['critical']}")
    print(f"  High:       {result.summary['by_severity']['high']}")
    print(f"  Medium:     {result.summary['by_severity']['medium']}")
    print(f"  Low:        {result.summary['by_severity']['low']}")
    print(f"\nEstimated Effort: {result.summary['estimated_total_effort_hours']} hours")
    print("=" * 60)

    # Exit code based on critical issues
    if result.summary["by_severity"]["critical"] > 0:
        print(
            f"\nERROR: {result.summary['by_severity']['critical']} critical issues found!"
        )
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
