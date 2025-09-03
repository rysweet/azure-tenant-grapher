"""Data models for the Agentic Testing System."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TestStatus(Enum):
    """Test execution status."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    RUNNING = "running"
    PENDING = "pending"


class Priority(Enum):
    """Issue priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestInterface(Enum):
    """Test interface type."""

    CLI = "cli"
    GUI = "gui"
    MIXED = "mixed"
    API = "api"


@dataclass
class TestStep:
    """Single step in a test scenario."""

    action: str  # 'click', 'type', 'execute', 'wait', 'verify'
    target: str  # Element selector, command, or API endpoint
    value: Optional[str] = None  # Input value if needed
    wait_for: Optional[str] = None  # Condition to wait for
    timeout: Optional[int] = None  # Step-specific timeout
    description: Optional[str] = None
    expected: Optional[Any] = None  # Expected result for verification

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class VerificationStep:
    """Verification step for test results."""

    type: str  # 'text', 'element', 'value', 'screenshot', 'log'
    target: str  # What to verify
    expected: Any  # Expected value/state
    operator: str = "equals"  # 'equals', 'contains', 'matches', 'exists'
    description: Optional[str] = None


@dataclass
class TestScenario:
    """Represents a test scenario to execute."""

    id: str
    feature: str
    name: str
    description: str
    interface: TestInterface
    steps: List[TestStep]
    expected_outcome: str
    verification: List[VerificationStep]
    tags: List[str] = field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    timeout: int = 300  # seconds
    retry_on_failure: bool = True
    dependencies: List[str] = field(default_factory=list)  # Other scenario IDs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "feature": self.feature,
            "name": self.name,
            "description": self.description,
            "interface": self.interface.value,
            "steps": [step.to_dict() for step in self.steps],
            "expected_outcome": self.expected_outcome,
            "verification": [v.__dict__ for v in self.verification],
            "tags": self.tags,
            "priority": self.priority.value,
            "timeout": self.timeout,
            "retry_on_failure": self.retry_on_failure,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestScenario":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            feature=data["feature"],
            name=data["name"],
            description=data["description"],
            interface=TestInterface(data["interface"]),
            steps=[TestStep(**s) for s in data["steps"]],
            expected_outcome=data["expected_outcome"],
            verification=[VerificationStep(**v) for v in data["verification"]],
            tags=data.get("tags", []),
            priority=Priority(data.get("priority", "medium")),
            timeout=data.get("timeout", 300),
            retry_on_failure=data.get("retry_on_failure", True),
            dependencies=data.get("dependencies", []),
        )


@dataclass
class TestError:
    """Represents an error during test execution."""

    type: str  # 'assertion', 'timeout', 'crash', 'network', etc.
    message: str
    stack_trace: Optional[str] = None
    screenshot: Optional[str] = None  # Path to screenshot
    logs: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CommandResult:
    """Result of executing a CLI command."""

    command: str
    args: List[str]
    stdout: str
    stderr: str
    returncode: int
    duration: float  # seconds
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success(self) -> bool:
        """Check if command succeeded."""
        return self.returncode == 0


@dataclass
class TestResult:
    """Result of executing a test scenario."""

    scenario_id: str
    status: TestStatus
    duration: float  # seconds
    error: Optional[TestError] = None
    screenshots: List[str] = field(default_factory=list)
    logs: str = ""
    command_results: List[CommandResult] = field(default_factory=list)
    verification_results: Dict[str, bool] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "scenario_id": self.scenario_id,
            "status": self.status.value,
            "duration": self.duration,
            "error": self.error.__dict__ if self.error else None,
            "screenshots": self.screenshots,
            "logs": self.logs,
            "verification_results": self.verification_results,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
        }


@dataclass
class TestFailure:
    """Represents a test failure that needs reporting."""

    feature: str
    scenario: str
    scenario_id: str
    error_message: str
    error_type: str
    stack_trace: Optional[str] = None
    screenshot: Optional[str] = None  # Path to screenshot file
    reproduction_steps: List[str] = field(default_factory=list)
    expected_behavior: str = ""
    actual_behavior: str = ""
    environment: Dict[str, str] = field(default_factory=dict)
    logs: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def generate_fingerprint(self) -> str:
        """Generate unique fingerprint for deduplication."""
        content = f"{self.feature}:{self.scenario}:{self.error_type}:{self.error_message[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()

    def to_github_issue(self) -> Dict[str, Any]:
        """Format as GitHub issue."""
        return {
            "title": f"[Test Failure] {self.feature}: {self.error_message[:80]}",
            "body": self._format_issue_body(),
            "labels": ["bug", "test-failure", f"feature:{self.feature}"],
        }

    def _format_issue_body(self) -> str:
        """Format detailed issue body."""
        body = f"""## Test Failure Report

**Feature**: {self.feature}
**Scenario**: {self.scenario}
**Timestamp**: {self.timestamp.isoformat()}

## Error Details

**Type**: {self.error_type}
**Message**: {self.error_message}

## Reproduction Steps

{self._format_steps()}

## Expected Behavior

{self.expected_behavior}

## Actual Behavior

{self.actual_behavior}

## Environment

{self._format_environment()}

## Stack Trace

```
{self.stack_trace or "No stack trace available"}
```

## Logs

<details>
<summary>Click to expand logs</summary>

```
{self.logs or "No logs available"}
```

</details>

## Screenshots

{self._format_screenshot_link()}

---
*Generated by Agentic Testing System*
*Scenario ID: {self.scenario_id}*
"""
        return body

    def _format_steps(self) -> str:
        """Format reproduction steps."""
        if not self.reproduction_steps:
            return "No reproduction steps available"

        return "\n".join(
            f"{i + 1}. {step}" for i, step in enumerate(self.reproduction_steps)
        )

    def _format_environment(self) -> str:
        """Format environment information."""
        if not self.environment:
            return "No environment information available"

        return "\n".join(f"- **{k}**: {v}" for k, v in self.environment.items())

    def _format_screenshot_link(self) -> str:
        """Format screenshot link for GitHub."""
        if not self.screenshot:
            return "No screenshot available"

        # This will be replaced with actual uploaded URL
        return f"![Screenshot]({self.screenshot})"


@dataclass
class FeatureSpec:
    """Specification of a feature derived from documentation."""

    name: str
    purpose: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    success_criteria: List[str]
    failure_modes: List[str]
    edge_cases: List[str]
    dependencies: List[str] = field(default_factory=list)

    @classmethod
    def from_llm_response(cls, response: str) -> "FeatureSpec":
        """Parse from LLM JSON response."""
        data = json.loads(response)
        return cls(**data)


@dataclass
class AppState:
    """Represents application state at a point in time."""

    timestamp: datetime
    interface: TestInterface
    screenshot_path: Optional[str] = None
    dom_snapshot: Optional[str] = None
    accessibility_tree: Optional[Dict] = None
    url: Optional[str] = None
    title: Optional[str] = None
    neo4j_stats: Optional[Dict[str, int]] = None
    active_processes: List[str] = field(default_factory=list)


@dataclass
class TestSession:
    """Represents a complete testing session."""

    id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    scenarios_executed: List[str] = field(default_factory=list)
    results: List[TestResult] = field(default_factory=list)
    failures: List[TestFailure] = field(default_factory=list)
    issues_created: List[str] = field(default_factory=list)  # GitHub issue numbers
    metrics: Dict[str, Any] = field(default_factory=dict)

    def calculate_metrics(self):
        """Calculate session metrics."""
        total = len(self.results)
        if total == 0:
            return

        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

        self.metrics = {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": passed / total * 100,
            "issues_created": len(self.issues_created),
            "duration": (self.end_time - self.start_time).total_seconds()
            if self.end_time
            else 0,
        }
