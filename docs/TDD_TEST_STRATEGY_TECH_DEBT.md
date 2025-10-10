# TDD Test Strategy for Technical Debt Elimination

## Executive Summary

This document defines a Test-Driven Development (TDD) approach to eliminate technical debt in the Azure Tenant Grapher codebase. Following TDD principles, **ALL tests will be written FIRST and will FAIL initially**, then implementation will make them pass.

## Problem Areas Identified

### 1. E2E Test Collection Failures
- **auth_security**: Missing `NoEncryptionAvailable` from cryptography
- **lifecycle**: Missing `playwright` dependency
- **neo4j_integration**: Missing `Neo4jContainer` import
- **spa_tabs**: Missing `playwright` dependency

### 2. Debug Print Statements (5 files affected)
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/cli_commands.py` (30+ print statements)
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/tenant_creator.py`
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/container_manager.py`
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/resource_processor.py`

### 3. Empty Exception Handlers (7 files affected)
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/iac/subset.py`
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/cli_commands.py`
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/terraform_destroyer.py`
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/commands/list_deployments.py`
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/agent_mode.py`
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/threat_modeling_agent/tmt_runner.py`
- `/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/src/resource_processor.py`

### 4. Missing Dependencies
- `playwright` (for E2E SPA tests)
- Correct `cryptography` API usage
- `testcontainers` may not be properly configured

---

## Phase 1: Test Collection Validation Tests (Unit - 60%)

### Objective
Ensure all test modules can be collected and imported without errors.

### Test File: `tests/test_meta_collection.py`

**Test Specifications:**

```python
"""Meta-tests that validate test suite integrity."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


class TestTestCollectionIntegrity:
    """Verify all test files can be collected successfully."""

    def test_all_e2e_tests_can_be_collected(self):
        """
        FAILING TEST: Verify E2E tests collect without import errors.

        Expected to FAIL initially due to missing dependencies.
        """
        result = subprocess.run(
            ["uv", "run", "pytest", "tests/e2e/", "--collect-only", "-q"],
            capture_output=True,
            text=True,
        )

        # Should have NO errors
        assert "ERROR" not in result.stdout
        assert "ImportError" not in result.stdout
        assert "ModuleNotFoundError" not in result.stdout
        assert "NameError" not in result.stdout
        assert result.returncode == 0, f"Collection failed: {result.stdout}\n{result.stderr}"

    def test_auth_security_tests_import_successfully(self):
        """
        FAILING TEST: auth_security conftest should import without cryptography errors.

        Expected to FAIL: NoEncryptionAvailable import error.
        """
        conftest_path = Path("tests/e2e/auth_security/conftest.py")
        spec = importlib.util.spec_from_file_location("auth_conftest", conftest_path)
        module = importlib.util.module_from_spec(spec)

        # Should not raise ImportError
        try:
            spec.loader.exec_module(module)
            assert hasattr(module, "mock_rsa_keys")
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")

    def test_lifecycle_tests_import_successfully(self):
        """
        FAILING TEST: lifecycle tests should import without playwright errors.

        Expected to FAIL: ModuleNotFoundError for playwright.
        """
        test_path = Path("tests/e2e/lifecycle/test_complete_lifecycle.py")
        spec = importlib.util.spec_from_file_location("lifecycle_test", test_path)
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
            assert hasattr(module, "TestCompleteTenantLifecycle")
        except ModuleNotFoundError as e:
            pytest.fail(f"Module not found: {e}")

    def test_spa_tabs_tests_import_successfully(self):
        """
        FAILING TEST: SPA tabs tests should import without playwright errors.

        Expected to FAIL: ModuleNotFoundError for playwright.
        """
        result = subprocess.run(
            ["uv", "run", "pytest", "tests/e2e/spa_tabs/", "--collect-only", "-q"],
            capture_output=True,
            text=True,
        )

        assert "ModuleNotFoundError" not in result.stdout
        assert result.returncode == 0

    def test_neo4j_integration_tests_import_successfully(self):
        """
        FAILING TEST: Neo4j integration tests should import without NameError.

        Expected to FAIL: NameError for Neo4jContainer.
        """
        conftest_path = Path("tests/e2e/neo4j_integration/conftest.py")
        spec = importlib.util.spec_from_file_location("neo4j_conftest", conftest_path)
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except NameError as e:
            pytest.fail(f"NameError during import: {e}")

    @pytest.mark.parametrize("test_dir", [
        "tests/e2e/agent_mode",
        "tests/e2e/auth_security",
        "tests/e2e/lifecycle",
        "tests/e2e/neo4j_integration",
        "tests/e2e/spa_tabs",
    ])
    def test_e2e_subdirectory_collects_without_errors(self, test_dir):
        """
        FAILING TEST: Each E2E subdirectory should collect cleanly.

        Expected to FAIL for directories with missing dependencies.
        """
        result = subprocess.run(
            ["uv", "run", "pytest", test_dir, "--collect-only"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed to collect {test_dir}: {result.stdout}"
        assert "error" not in result.stdout.lower()


class TestDependencyInstallation:
    """Verify all required dependencies are installable."""

    def test_playwright_is_installed(self):
        """
        FAILING TEST: Playwright should be importable.

        Expected to FAIL: ModuleNotFoundError.
        """
        try:
            import playwright
            assert playwright is not None
        except ModuleNotFoundError:
            pytest.fail("playwright module not found")

    def test_playwright_browsers_installed(self):
        """
        FAILING TEST: Playwright browsers should be installed.

        Expected to FAIL: Browsers not installed.
        """
        result = subprocess.run(
            ["playwright", "install", "--dry-run"],
            capture_output=True,
            text=True,
        )
        # After implementation, this should show browsers are already installed
        assert result.returncode == 0

    def test_cryptography_has_correct_api(self):
        """
        FAILING TEST: Cryptography should support NoEncryption (not NoEncryptionAvailable).

        Expected to FAIL: Import uses deprecated API.
        """
        from cryptography.hazmat.primitives.serialization import NoEncryption
        assert NoEncryption is not None

    def test_testcontainers_neo4j_available(self):
        """
        FAILING TEST: testcontainers[neo4j] should be available.

        Expected to FAIL: May not be installed correctly.
        """
        try:
            from testcontainers.neo4j import Neo4jContainer
            assert Neo4jContainer is not None
        except (ImportError, ModuleNotFoundError):
            pytest.fail("testcontainers.neo4j not available")
```

**Coverage Target:** 100% of E2E test directories
**Pyramid Level:** Unit (60%)

---

## Phase 2: Logging Standards Validation Tests (Unit - 60%)

### Objective
Enforce structured logging using `structlog` and eliminate debug print statements.

### Test File: `tests/test_meta_logging_standards.py`

**Test Specifications:**

```python
"""Meta-tests that enforce logging standards across the codebase."""

import ast
import re
from pathlib import Path
from typing import List, Tuple

import pytest


class LoggingViolation:
    """Represents a logging standard violation."""

    def __init__(self, file_path: str, line_num: int, violation_type: str, code: str):
        self.file_path = file_path
        self.line_num = line_num
        self.violation_type = violation_type
        self.code = code

    def __repr__(self):
        return f"{self.file_path}:{self.line_num} - {self.violation_type}: {self.code}"


class TestLoggingStandards:
    """Enforce structured logging standards across production code."""

    def test_no_debug_print_statements_in_src(self):
        """
        FAILING TEST: No print(...DEBUG...) statements should exist in src/.

        Expected to FAIL: 30+ debug prints in cli_commands.py and others.
        """
        violations = self._find_debug_prints("src")

        assert len(violations) == 0, (
            f"Found {len(violations)} DEBUG print statements:\n" +
            "\n".join(str(v) for v in violations[:10])
        )

    def test_no_bare_print_in_production_modules(self):
        """
        FAILING TEST: Production modules should not use bare print() except for CLI output.

        Expected to FAIL: Many print statements in src/.

        Exceptions:
        - cli_commands.py (allowed for user-facing CLI output)
        - Scripts directory (allowed)
        """
        violations = self._find_bare_prints("src")

        # Filter out allowed files
        allowed_files = {"cli_commands.py", "scripts/"}
        violations = [
            v for v in violations
            if not any(allowed in v.file_path for allowed in allowed_files)
        ]

        assert len(violations) == 0, (
            f"Found {len(violations)} bare print() calls:\n" +
            "\n".join(str(v) for v in violations[:10])
        )

    def test_all_production_code_uses_structlog(self):
        """
        FAILING TEST: All modules in src/ should import and use structlog.

        Expected to FAIL: Only 5 files currently use structlog.
        """
        src_files = list(Path("src").rglob("*.py"))
        violations = []

        for file_path in src_files:
            if file_path.name == "__init__.py":
                continue

            content = file_path.read_text()

            # Check for structlog import
            has_structlog = (
                "import structlog" in content or
                "from structlog import" in content
            )

            # Check if file has logging needs (functions with logger calls or exceptions)
            has_logging_needs = (
                "logger." in content or
                "except" in content or
                ".error(" in content or
                ".info(" in content or
                ".warning(" in content
            )

            if has_logging_needs and not has_structlog:
                violations.append(file_path)

        assert len(violations) == 0, (
            f"Found {len(violations)} files without structlog:\n" +
            "\n".join(str(v) for v in violations)
        )

    def test_logger_instantiation_follows_pattern(self):
        """
        FAILING TEST: All logger instantiations should follow structlog pattern.

        Pattern: logger = structlog.get_logger(__name__)

        Expected to FAIL: Some files may use different patterns.
        """
        violations = []
        src_files = list(Path("src").rglob("*.py"))

        for file_path in src_files:
            if file_path.name == "__init__.py":
                continue

            content = file_path.read_text()

            if "structlog" not in content:
                continue

            # Check for proper logger instantiation
            correct_pattern = r"logger\s*=\s*structlog\.get_logger\(__name__\)"

            # Check for alternative patterns that are incorrect
            wrong_patterns = [
                r"logger\s*=\s*logging\.getLogger",
                r"logger\s*=\s*structlog\.getLogger\(['\"]",
            ]

            for pattern in wrong_patterns:
                if re.search(pattern, content):
                    violations.append((file_path, pattern))

        assert len(violations) == 0, (
            f"Found {len(violations)} incorrect logger patterns:\n" +
            "\n".join(f"{path}: {pattern}" for path, pattern in violations)
        )

    def test_no_flush_true_in_print_statements(self):
        """
        FAILING TEST: No print statements with flush=True (indicates debug code).

        Expected to FAIL: Multiple flush=True in cli_commands.py.
        """
        violations = []
        src_files = list(Path("src").rglob("*.py"))

        for file_path in src_files:
            content = file_path.read_text()
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                if "print(" in line and "flush=True" in line:
                    violations.append(
                        LoggingViolation(
                            str(file_path), line_num, "flush=True", line.strip()
                        )
                    )

        assert len(violations) == 0, (
            f"Found {len(violations)} print(flush=True) calls:\n" +
            "\n".join(str(v) for v in violations)
        )

    def _find_debug_prints(self, directory: str) -> List[LoggingViolation]:
        """Find all print statements containing 'DEBUG'."""
        violations = []
        path = Path(directory)

        for file_path in path.rglob("*.py"):
            content = file_path.read_text()
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                if "print(" in line and "DEBUG" in line:
                    violations.append(
                        LoggingViolation(
                            str(file_path), line_num, "DEBUG print", line.strip()
                        )
                    )

        return violations

    def _find_bare_prints(self, directory: str) -> List[LoggingViolation]:
        """Find all bare print() statements."""
        violations = []
        path = Path(directory)

        for file_path in path.rglob("*.py"):
            content = file_path.read_text()

            try:
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == "print":
                            violations.append(
                                LoggingViolation(
                                    str(file_path),
                                    node.lineno,
                                    "bare print()",
                                    ast.unparse(node)
                                )
                            )
            except SyntaxError:
                continue  # Skip files with syntax errors

        return violations


class TestLogOutputFormat:
    """Verify that structured logging produces correct JSON output."""

    def test_structlog_outputs_json_format(self, tmp_path):
        """
        FAILING TEST: Structlog should output structured JSON logs.

        Expected to FAIL: May need configuration.
        """
        import json
        import structlog
        from io import StringIO

        # Capture log output
        output = StringIO()

        # Configure structlog for JSON output
        structlog.configure(
            processors=[
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=True,
        )

        logger = structlog.get_logger()
        logger.info("test_message", key="value", count=42)

        # Parse output as JSON
        log_output = output.getvalue().strip()
        try:
            parsed = json.loads(log_output)
            assert parsed["event"] == "test_message"
            assert parsed["key"] == "value"
            assert parsed["count"] == 42
        except json.JSONDecodeError:
            pytest.fail(f"Log output is not valid JSON: {log_output}")

    def test_logger_includes_context(self):
        """
        FAILING TEST: Logger should include context in all log messages.

        Expected to FAIL: Need to verify context is included.
        """
        import structlog
        from io import StringIO

        output = StringIO()
        structlog.configure(
            processors=[
                structlog.processors.JSONRenderer()
            ],
            logger_factory=structlog.PrintLoggerFactory(file=output),
        )

        logger = structlog.get_logger()
        bound_logger = logger.bind(request_id="test-123", user="test-user")
        bound_logger.info("operation_complete")

        import json
        parsed = json.loads(output.getvalue().strip())
        assert parsed["request_id"] == "test-123"
        assert parsed["user"] == "test-user"
```

**Coverage Target:** 100% of src/ files
**Pyramid Level:** Unit (60%)

---

## Phase 3: Exception Handling Validation Tests (Unit/Integration - 60%/30%)

### Objective
Ensure all exceptions are logged with context and critical exceptions propagate correctly.

### Test File: `tests/test_meta_exception_handling.py`

**Test Specifications:**

```python
"""Meta-tests that enforce exception handling standards."""

import ast
import re
from pathlib import Path
from typing import List, Tuple

import pytest


class ExceptionHandlingViolation:
    """Represents an exception handling violation."""

    def __init__(self, file_path: str, line_num: int, violation_type: str, code: str):
        self.file_path = file_path
        self.line_num = line_num
        self.violation_type = violation_type
        self.code = code

    def __repr__(self):
        return f"{self.file_path}:{self.line_num} - {self.violation_type}"


class TestExceptionHandlingStandards:
    """Enforce exception handling standards across production code."""

    def test_no_bare_except_pass_in_src(self):
        """
        FAILING TEST: No 'except: pass' blocks should exist in src/.

        Expected to FAIL: 7 files have bare except: pass.
        """
        violations = self._find_bare_except_pass("src")

        assert len(violations) == 0, (
            f"Found {len(violations)} bare 'except: pass' blocks:\n" +
            "\n".join(str(v) for v in violations)
        )

    def test_all_exceptions_are_logged_in_src(self):
        """
        FAILING TEST: All exception handlers should log the exception.

        Expected to FAIL: Many except blocks don't log.
        """
        violations = self._find_unlogged_exceptions("src")

        # Allow some specific patterns (e.g., CancelledError, KeyboardInterrupt)
        allowed_exceptions = {"CancelledError", "KeyboardInterrupt", "EOFError"}
        violations = [
            v for v in violations
            if not any(exc in v.code for exc in allowed_exceptions)
        ]

        assert len(violations) == 0, (
            f"Found {len(violations)} exception handlers without logging:\n" +
            "\n".join(str(v) for v in violations[:10])
        )

    def test_exception_logging_includes_context(self):
        """
        FAILING TEST: Exception logging should include context (exc_info, resource IDs, etc).

        Expected to FAIL: Many logs don't include context.
        """
        violations = []
        src_files = list(Path("src").rglob("*.py"))

        for file_path in src_files:
            content = file_path.read_text()

            # Find logger.exception() or logger.error() in except blocks
            except_blocks = re.finditer(
                r'except\s+\w+(?:\s+as\s+\w+)?:\s*\n((?:\s{4,}.*\n)*)',
                content,
                re.MULTILINE
            )

            for match in except_blocks:
                block = match.group(1)

                # Check if logger call includes exc_info or context
                has_logger = "logger." in block
                has_exc_info = "exc_info=True" in block
                has_exception = "logger.exception" in block
                has_context = re.search(r'[\w_]+=', block)

                if has_logger and not (has_exc_info or has_exception or has_context):
                    violations.append(file_path)

        assert len(violations) == 0, (
            f"Found {len(violations)} exception handlers without context:\n" +
            "\n".join(str(v) for v in violations[:10])
        )

    def test_critical_exceptions_propagate(self):
        """
        FAILING TEST: Critical exceptions (SystemExit, KeyboardInterrupt) should propagate.

        Expected to FAIL: Some handlers may catch these.
        """
        violations = []
        src_files = list(Path("src").rglob("*.py"))

        for file_path in src_files:
            content = file_path.read_text()

            # Find bare except: that would catch everything
            bare_except = re.finditer(r'except\s*:', content)

            for match in bare_except:
                violations.append(
                    ExceptionHandlingViolation(
                        str(file_path),
                        content[:match.start()].count('\n') + 1,
                        "bare except:",
                        "catches all exceptions including critical ones"
                    )
                )

        assert len(violations) == 0, (
            f"Found {len(violations)} bare except: handlers:\n" +
            "\n".join(str(v) for v in violations)
        )

    def test_no_silent_exception_swallowing(self):
        """
        FAILING TEST: Exception handlers should not silently swallow errors.

        A handler is considered 'silent' if it:
        1. Catches an exception
        2. Does nothing (pass) or minimal action
        3. Does not re-raise or return error status

        Expected to FAIL: Many handlers just pass.
        """
        violations = []
        src_files = list(Path("src").rglob("*.py"))

        for file_path in src_files:
            try:
                content = file_path.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler):
                        # Check if handler body is just 'pass' or empty
                        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                            violations.append(
                                ExceptionHandlingViolation(
                                    str(file_path),
                                    node.lineno,
                                    "silent exception",
                                    "except block only contains 'pass'"
                                )
                            )
            except SyntaxError:
                continue

        assert len(violations) == 0, (
            f"Found {len(violations)} silent exception handlers:\n" +
            "\n".join(str(v) for v in violations[:10])
        )

    def _find_bare_except_pass(self, directory: str) -> List[ExceptionHandlingViolation]:
        """Find all 'except: pass' patterns."""
        violations = []
        path = Path(directory)

        for file_path in path.rglob("*.py"):
            content = file_path.read_text()
            lines = content.split("\n")

            for i, line in enumerate(lines):
                # Look for 'except:' followed by 'pass' on next line
                if "except" in line and ":" in line:
                    # Check if next non-empty line is 'pass'
                    for j in range(i + 1, min(i + 5, len(lines))):
                        next_line = lines[j].strip()
                        if next_line:
                            if next_line == "pass":
                                violations.append(
                                    ExceptionHandlingViolation(
                                        str(file_path),
                                        i + 1,
                                        "except: pass",
                                        f"{line.strip()} -> {next_line}"
                                    )
                                )
                            break

        return violations

    def _find_unlogged_exceptions(self, directory: str) -> List[ExceptionHandlingViolation]:
        """Find exception handlers without logging."""
        violations = []
        path = Path(directory)

        for file_path in path.rglob("*.py"):
            try:
                content = file_path.read_text()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler):
                        # Check if handler body contains logger call
                        has_logger = False

                        for child in ast.walk(node):
                            if isinstance(child, ast.Attribute):
                                if (hasattr(child.value, 'id') and
                                    child.value.id == 'logger'):
                                    has_logger = True
                                    break

                        if not has_logger and len(node.body) > 1:
                            violations.append(
                                ExceptionHandlingViolation(
                                    str(file_path),
                                    node.lineno,
                                    "unlogged exception",
                                    ast.unparse(node)[:50]
                                )
                            )
            except SyntaxError:
                continue

        return violations


class TestExceptionHandlingIntegration:
    """Integration tests for exception handling behavior."""

    @pytest.mark.asyncio
    async def test_resource_processor_logs_exceptions(self, mock_neo4j_connection):
        """
        FAILING TEST: ResourceProcessor should log all exceptions with context.

        Expected to FAIL: Current code has except: pass blocks.
        """
        from unittest.mock import MagicMock, patch
        from src.resource_processor import ResourceProcessor

        mock_session_manager = MagicMock()
        processor = ResourceProcessor(mock_session_manager)

        # Cause an error
        with patch.object(processor.db_ops, 'upsert_resource', side_effect=Exception("Test error")):
            result = processor.db_ops.upsert_resource({"id": "test", "name": "test"})

            # Should return False, not raise
            assert result is False

    def test_container_manager_logs_docker_errors(self):
        """
        FAILING TEST: ContainerManager should log Docker errors with context.

        Expected to FAIL: May have silent error handling.
        """
        from unittest.mock import MagicMock, patch
        from src.container_manager import ContainerManager

        with patch('docker.from_env', side_effect=Exception("Docker not available")):
            manager = ContainerManager()
            # Should log error, not crash
            # Implementation should gracefully handle missing Docker

    def test_cli_commands_propagate_critical_errors(self):
        """
        FAILING TEST: CLI commands should propagate critical errors to user.

        Expected to FAIL: Some errors may be swallowed.
        """
        # This will be implemented after seeing the pattern
        pass
```

**Coverage Target:** 100% of exception handlers
**Pyramid Level:** Unit (60%) + Integration (30%)

---

## Phase 4: Integration Tests (30%)

### Test File: `tests/integration/test_logging_integration.py`

**Test Specifications:**

```python
"""Integration tests for logging behavior across components."""

import json
import logging
import subprocess
from io import StringIO
from pathlib import Path

import pytest
import structlog


class TestLoggingIntegration:
    """Test logging behavior in realistic scenarios."""

    def test_debug_flag_enables_debug_logging(self, tmp_path):
        """
        FAILING TEST: --debug flag should enable DEBUG level logs.

        Expected to FAIL: Need to verify backward compatibility.
        """
        # Run CLI with --debug flag
        result = subprocess.run(
            ["uv", "run", "atg", "--debug", "--help"],
            capture_output=True,
            text=True,
        )

        # Should not error
        assert result.returncode == 0

    def test_structured_logs_in_cli_commands(self, tmp_path):
        """
        FAILING TEST: CLI commands should output structured logs.

        Expected to FAIL: Current print statements don't create structured logs.
        """
        log_file = tmp_path / "test.log"

        # Configure logging to file
        # Run a CLI command
        # Verify log file contains structured JSON

        # This will be implemented based on CLI structure

    def test_exception_logging_includes_stack_trace(self):
        """
        FAILING TEST: Exception logs should include full stack traces.

        Expected to FAIL: Need to ensure exc_info=True is used.
        """
        import structlog
        from io import StringIO

        output = StringIO()
        structlog.configure(
            processors=[
                structlog.processors.ExceptionPrettyPrinter(),
                structlog.processors.JSONRenderer()
            ],
            logger_factory=structlog.PrintLoggerFactory(file=output),
        )

        logger = structlog.get_logger()

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger.exception("caught_error")

        log_output = output.getvalue()
        assert "ValueError" in log_output
        assert "Test exception" in log_output

    def test_logging_does_not_break_existing_functionality(self):
        """
        FAILING TEST: Replacing print with logging should not break features.

        Expected to FAIL: Need integration tests for each module.
        """
        # This will test specific scenarios
        pass

    @pytest.mark.asyncio
    async def test_async_logging_is_thread_safe(self):
        """
        FAILING TEST: Logging in async contexts should be thread-safe.

        Expected to FAIL: Need to verify structlog configuration.
        """
        import asyncio
        import structlog

        logger = structlog.get_logger()

        async def log_task(task_id: int):
            for i in range(10):
                logger.info("task_iteration", task_id=task_id, iteration=i)
                await asyncio.sleep(0.01)

        # Run multiple tasks concurrently
        tasks = [log_task(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Should not raise or deadlock


class TestExceptionHandlingIntegration:
    """Integration tests for exception handling."""

    def test_neo4j_connection_errors_logged_properly(self, tmp_path):
        """
        FAILING TEST: Neo4j connection errors should be logged with context.

        Expected to FAIL: May have silent failures.
        """
        from unittest.mock import MagicMock, patch

        with patch('neo4j.GraphDatabase.driver', side_effect=Exception("Connection failed")):
            # Try to connect
            # Verify error is logged with context
            pass

    def test_azure_api_errors_logged_with_retry_context(self):
        """
        FAILING TEST: Azure API errors should log retry attempts.

        Expected to FAIL: May not include retry context.
        """
        # Test retry logic logs each attempt
        pass

    def test_resource_processing_errors_dont_stop_pipeline(self):
        """
        FAILING TEST: Single resource errors shouldn't stop entire pipeline.

        Expected to FAIL: Need to verify error handling.
        """
        # Test that processing continues after error
        pass
```

**Coverage Target:** 70% of critical integration paths
**Pyramid Level:** Integration (30%)

---

## Phase 5: E2E Tests (10%)

### Test File: `tests/e2e/test_logging_e2e.py`

**Test Specifications:**

```python
"""End-to-end tests for logging behavior."""

import json
import subprocess
from pathlib import Path

import pytest


class TestLoggingE2E:
    """E2E tests for complete logging workflows."""

    def test_full_scan_produces_structured_logs(self, tmp_path):
        """
        FAILING TEST: Full tenant scan should produce structured logs.

        Expected to FAIL: Current implementation uses print statements.
        """
        log_file = tmp_path / "scan.log"

        # Run full scan with logging to file
        # Verify all logs are structured JSON
        # Verify no DEBUG prints leaked through

        if log_file.exists():
            content = log_file.read_text()
            lines = [line for line in content.split('\n') if line.strip()]

            for line in lines:
                # Should be valid JSON
                try:
                    parsed = json.loads(line)
                    assert "event" in parsed
                    assert "timestamp" in parsed or "time" in parsed
                except json.JSONDecodeError:
                    pytest.fail(f"Non-JSON log line: {line}")

    def test_error_recovery_logged_completely(self):
        """
        FAILING TEST: Error recovery should log all steps.

        Expected to FAIL: May have gaps in error logging.
        """
        # Cause an error scenario
        # Verify error, recovery attempt, and outcome are all logged
        pass

    def test_no_print_statements_leak_to_stdout(self, tmp_path):
        """
        FAILING TEST: No debug print statements should appear in output.

        Expected to FAIL: DEBUG prints currently leak.
        """
        result = subprocess.run(
            ["uv", "run", "atg", "--help"],
            capture_output=True,
            text=True,
        )

        # Should not contain DEBUG
        assert "DEBUG" not in result.stdout
        assert "DEBUG" not in result.stderr
        assert "[DEBUG]" not in result.stdout
        assert "[DEBUG]" not in result.stderr
```

**Coverage Target:** 100% of user-facing workflows
**Pyramid Level:** E2E (10%)

---

## Test Pyramid Distribution

```
       E2E (10%)
      /-----------\
     | 10-15 tests |  test_logging_e2e.py
     |             |  E2E workflow validation
    /---------------\
   /                 \
  / Integration (30%) \
 /---------------------\
| 30-40 tests          |  test_logging_integration.py
| Component integration |  test_exception_handling_integration.py
|-----------------------|
|                       |
|    Unit (60%)         |
|  60-80 tests          |
| test_meta_collection.py
| test_meta_logging_standards.py
| test_meta_exception_handling.py
|_______________________|
```

---

## Mock and Fixture Requirements

### New Fixtures Needed

**File: `tests/conftest.py` (additions)**

```python
import pytest
import structlog
from io import StringIO
from unittest.mock import MagicMock


@pytest.fixture
def structlog_test_logger():
    """Provide a structlog logger configured for testing."""
    output = StringIO()
    structlog.configure(
        processors=[
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.PrintLoggerFactory(file=output),
        cache_logger_on_first_use=False,
    )

    logger = structlog.get_logger()
    yield logger, output

    # Reset configuration
    structlog.reset_defaults()


@pytest.fixture
def capture_logs():
    """Fixture to capture all log output for testing."""
    output = StringIO()

    # Configure root logger to write to StringIO
    handler = logging.StreamHandler(output)
    logging.root.addHandler(handler)

    yield output

    logging.root.removeHandler(handler)


@pytest.fixture
def mock_azure_client():
    """Mock Azure client for testing."""
    mock = MagicMock()
    mock.discover_resources = MagicMock(return_value=[])
    return mock


@pytest.fixture
def mock_neo4j_connection():
    """Mock Neo4j connection for testing."""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    return mock_driver, mock_session
```

---

## Implementation Order (TDD)

### Week 1: Test Infrastructure
1. **Day 1-2**: Write Phase 1 tests (test_meta_collection.py)
   - Run tests → ALL FAIL
   - Fix dependency issues (playwright, cryptography API)
   - Run tests → ALL PASS

2. **Day 3-4**: Write Phase 2 tests (test_meta_logging_standards.py)
   - Run tests → ALL FAIL
   - Document all violations

3. **Day 5**: Write Phase 3 tests (test_meta_exception_handling.py)
   - Run tests → ALL FAIL
   - Document all violations

### Week 2: Fix Logging Issues
4. **Day 6-7**: Fix cli_commands.py
   - Tests still failing
   - Replace print statements with structlog
   - Run tests → Some pass

5. **Day 8-9**: Fix remaining files with print statements
   - tenant_creator.py
   - container_manager.py
   - resource_processor.py
   - Run tests → More pass

6. **Day 10**: Fix all logging standard violations
   - Run tests → All Phase 2 tests PASS

### Week 3: Fix Exception Handling
7. **Day 11-12**: Fix resource_processor.py exception handling
   - Add logging to all except blocks
   - Add context to all exception logs
   - Run tests → Some pass

8. **Day 13-14**: Fix remaining exception handling
   - Fix all 7 files with except: pass
   - Add proper error context
   - Run tests → All Phase 3 tests PASS

9. **Day 15**: Write and run integration tests (Phase 4)
   - Run tests → Some fail
   - Fix integration issues
   - Run tests → All pass

### Week 4: E2E and Validation
10. **Day 16-17**: Write and run E2E tests (Phase 5)
    - Run tests → Some fail
    - Fix E2E issues
    - Run tests → All pass

11. **Day 18-19**: Full validation
    - Run ALL tests
    - Fix any regressions
    - Achieve target coverage

12. **Day 20**: Documentation and cleanup
    - Update CLAUDE.md
    - Document logging patterns
    - Create migration guide

---

## Success Criteria

### Phase 1: Test Collection (MUST PASS)
- ✅ All E2E tests collect without errors
- ✅ No ImportError, ModuleNotFoundError, or NameError
- ✅ pytest exit code 0 for collection

### Phase 2: Logging Standards (MUST PASS)
- ✅ Zero DEBUG print statements in src/
- ✅ All production modules use structlog
- ✅ All logs are structured JSON
- ✅ Zero print(flush=True) in src/ (except CLI output)

### Phase 3: Exception Handling (MUST PASS)
- ✅ Zero bare "except: pass" in src/
- ✅ All exceptions logged with context
- ✅ All exception logs include exc_info or logger.exception()
- ✅ Critical exceptions (SystemExit, KeyboardInterrupt) propagate

### Phase 4: Integration (70% PASS RATE)
- ✅ --debug flag works correctly
- ✅ Async logging is thread-safe
- ✅ Exception logging doesn't break functionality

### Phase 5: E2E (100% PASS RATE)
- ✅ No DEBUG prints in CLI output
- ✅ All logs are structured
- ✅ Full workflows produce complete logs

### Coverage Targets
- **Unit Tests**: 60% of test suite (target: 60-80 tests)
- **Integration Tests**: 30% of test suite (target: 30-40 tests)
- **E2E Tests**: 10% of test suite (target: 10-15 tests)
- **Code Coverage**: Maintain ≥40% (per pyproject.toml)
- **Fixed Code Coverage**: 100% of modified code

---

## Risk Mitigation

### Risk: Breaking CLI User Experience
**Mitigation**:
- Create CLI output tests FIRST
- Ensure user-facing messages remain identical
- Add backward compatibility tests

### Risk: Performance Impact from Structured Logging
**Mitigation**:
- Benchmark logging performance
- Use async logging where appropriate
- Add performance tests

### Risk: Test Suite Takes Too Long
**Mitigation**:
- Parallelize tests with pytest-xdist
- Use pytest markers for fast/slow tests
- Mock heavy operations

### Risk: Flaky E2E Tests
**Mitigation**:
- Use testcontainers for isolation
- Add explicit waits and retries
- Mark flaky tests with pytest-rerunfailures

---

## Dependencies to Add

```toml
# Add to pyproject.toml [tool.uv.dev-dependencies]
playwright = ">=1.40.0"
pytest-xdist = ">=3.5.0"
pytest-benchmark = ">=4.0.0"
pytest-rerunfailures = ">=13.0"
```

**Installation Steps:**
```bash
# Add dependencies
uv add --dev playwright pytest-xdist pytest-benchmark pytest-rerunfailures

# Install Playwright browsers
uv run playwright install

# Verify cryptography version
uv run python -c "from cryptography.hazmat.primitives.serialization import NoEncryption; print('OK')"
```

---

## Validation Commands

```bash
# Run all meta-tests (should FAIL initially)
uv run pytest tests/test_meta_*.py -v

# Run only collection tests
uv run pytest tests/test_meta_collection.py -v

# Run only logging tests
uv run pytest tests/test_meta_logging_standards.py -v

# Run only exception handling tests
uv run pytest tests/test_meta_exception_handling.py -v

# Run with coverage
uv run pytest tests/test_meta_*.py --cov=src --cov-report=term-missing

# Run full test suite
uv run pytest tests/ -v --cov=src --cov-report=html

# Check for debug prints (should find MANY initially)
grep -r "print.*DEBUG" src/

# Check for except: pass (should find MANY initially)
grep -A1 "except.*:" src/ | grep "pass"
```

---

## Documentation Updates Required

1. **CLAUDE.md**: Add logging standards section
2. **README.md**: Update development guidelines
3. **CONTRIBUTING.md**: Add TDD workflow
4. **docs/LOGGING.md**: Create logging guide (NEW FILE)
5. **docs/EXCEPTION_HANDLING.md**: Create exception handling guide (NEW FILE)

---

## Summary

This TDD strategy ensures:

1. ✅ **Tests written FIRST** - All tests fail initially
2. ✅ **Clear validation** - 100% automated verification
3. ✅ **Proper pyramid** - 60/30/10 distribution
4. ✅ **Full coverage** - All problem areas addressed
5. ✅ **No regressions** - Existing functionality preserved
6. ✅ **Maintainable** - Clear patterns for future development

**Total Estimated Tests**: 100-135 tests
- Unit: 60-80 tests
- Integration: 30-40 tests
- E2E: 10-15 tests

**Timeline**: 4 weeks with continuous validation
**Success Metric**: All tests pass, zero technical debt in targeted areas
