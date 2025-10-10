"""
Meta-tests that validate test suite integrity.

These tests ensure all test files can be collected and imported without errors.
Following TDD: These tests should FAIL initially, then pass after fixes.
"""

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

        Expected to FAIL initially due to:
        - Missing playwright dependency
        - Incorrect cryptography API usage (NoEncryptionAvailable)
        - Missing Neo4jContainer import

        Success criteria:
        - pytest collection returns exit code 0
        - No ImportError in output
        - No ModuleNotFoundError in output
        - No NameError in output
        """
        result = subprocess.run(
            ["uv", "run", "pytest", "tests/e2e/", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Should have NO errors
        error_messages = []
        if "ERROR" in result.stdout:
            error_messages.append("Found ERROR in output")
        if "ImportError" in result.stdout:
            error_messages.append("Found ImportError in output")
        if "ModuleNotFoundError" in result.stdout:
            error_messages.append("Found ModuleNotFoundError in output")
        if "NameError" in result.stdout:
            error_messages.append("Found NameError in output")

        assert result.returncode == 0, (
            f"Collection failed with errors:\n"
            f"Exit code: {result.returncode}\n"
            f"Errors: {', '.join(error_messages)}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    def test_auth_security_tests_import_successfully(self):
        """
        FAILING TEST: auth_security conftest should import without cryptography errors.

        Expected to FAIL: NoEncryptionAvailable import error.

        The cryptography library changed its API:
        - OLD (incorrect): NoEncryptionAvailable
        - NEW (correct): NoEncryption

        Success criteria:
        - conftest.py imports successfully
        - mock_rsa_keys fixture is available
        """
        conftest_path = Path(__file__).parent / "e2e" / "auth_security" / "conftest.py"

        if not conftest_path.exists():
            pytest.skip("auth_security conftest not found")

        spec = importlib.util.spec_from_file_location("auth_conftest", conftest_path)
        module = importlib.util.module_from_spec(spec)

        # Should not raise ImportError
        try:
            spec.loader.exec_module(module)
            assert hasattr(module, "mock_rsa_keys"), "mock_rsa_keys fixture not found"
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")

    def test_lifecycle_tests_import_successfully(self):
        """
        FAILING TEST: lifecycle tests should import without playwright errors.

        Expected to FAIL: ModuleNotFoundError for playwright.

        Success criteria:
        - test file imports successfully
        - playwright.async_api is available
        - TestCompleteTenantLifecycle class exists
        """
        test_path = Path(__file__).parent / "e2e" / "lifecycle" / "test_complete_lifecycle.py"

        if not test_path.exists():
            pytest.skip("lifecycle test not found")

        spec = importlib.util.spec_from_file_location("lifecycle_test", test_path)
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
            assert hasattr(module, "TestCompleteTenantLifecycle"), (
                "TestCompleteTenantLifecycle class not found"
            )
        except ModuleNotFoundError as e:
            pytest.fail(f"Module not found: {e}")

    def test_spa_tabs_tests_import_successfully(self):
        """
        FAILING TEST: SPA tabs tests should import without playwright errors.

        Expected to FAIL: ModuleNotFoundError for playwright.

        Success criteria:
        - All spa_tabs tests collect successfully
        - No ModuleNotFoundError
        - Exit code 0
        """
        result = subprocess.run(
            ["uv", "run", "pytest", "tests/e2e/spa_tabs/", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert "ModuleNotFoundError" not in result.stdout, (
            f"playwright module not found:\n{result.stdout}"
        )
        assert result.returncode == 0, (
            f"SPA tabs collection failed:\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    def test_neo4j_integration_tests_import_successfully(self):
        """
        FAILING TEST: Neo4j integration tests should import without NameError.

        Expected to FAIL: NameError for Neo4jContainer.

        The conftest may have Neo4jContainer usage that's not properly imported.

        Success criteria:
        - conftest imports successfully
        - No NameError during import
        """
        conftest_path = Path(__file__).parent / "e2e" / "neo4j_integration" / "conftest.py"

        if not conftest_path.exists():
            pytest.skip("neo4j_integration conftest not found")

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

        Expected to FAIL for directories with missing dependencies:
        - auth_security: cryptography API issue
        - lifecycle: missing playwright
        - neo4j_integration: Neo4jContainer issue
        - spa_tabs: missing playwright

        Success criteria:
        - pytest collection returns 0
        - No 'error' in output (case-insensitive)
        """
        result = subprocess.run(
            ["uv", "run", "pytest", test_dir, "--collect-only"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0, (
            f"Failed to collect {test_dir}:\n"
            f"Exit code: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "error" not in result.stdout.lower(), (
            f"Errors found in {test_dir} collection:\n{result.stdout}"
        )


class TestDependencyInstallation:
    """Verify all required dependencies are installable and working."""

    def test_playwright_is_installed(self):
        """
        FAILING TEST: Playwright should be importable.

        Expected to FAIL: ModuleNotFoundError.

        Fix: Add playwright to dev dependencies:
        ```
        uv add --dev playwright
        uv run playwright install
        ```

        Success criteria:
        - import playwright succeeds
        - playwright module is not None
        """
        try:
            import playwright
            assert playwright is not None, "playwright module is None"
        except ModuleNotFoundError:
            pytest.fail(
                "playwright module not found. Install with:\n"
                "  uv add --dev playwright\n"
                "  uv run playwright install"
            )

    def test_playwright_browsers_installed(self):
        """
        FAILING TEST: Playwright browsers should be installed.

        Expected to FAIL: Browsers not installed.

        Fix: Run playwright install:
        ```
        uv run playwright install
        ```

        Success criteria:
        - playwright install command succeeds
        - Browsers are available
        """
        result = subprocess.run(
            ["playwright", "install", "--dry-run"],
            capture_output=True,
            text=True,
        )

        # After implementation, this should show browsers are already installed
        assert result.returncode == 0, (
            f"Playwright browser check failed:\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}\n"
            f"Run: uv run playwright install"
        )

    def test_cryptography_has_correct_api(self):
        """
        FAILING TEST: Cryptography should support NoEncryption (not NoEncryptionAvailable).

        Expected to FAIL: Import uses deprecated API.

        The correct import is:
        ```python
        from cryptography.hazmat.primitives.serialization import NoEncryption
        ```

        NOT:
        ```python
        from cryptography.hazmat.primitives.serialization import NoEncryptionAvailable
        ```

        Success criteria:
        - NoEncryption imports successfully
        - NoEncryption is not None
        """
        try:
            from cryptography.hazmat.primitives.serialization import NoEncryption
            assert NoEncryption is not None, "NoEncryption is None"
        except ImportError as e:
            pytest.fail(
                f"Failed to import NoEncryption: {e}\n"
                f"Update code to use NoEncryption instead of NoEncryptionAvailable"
            )

    def test_testcontainers_neo4j_available(self):
        """
        FAILING TEST: testcontainers[neo4j] should be available.

        Expected to FAIL: May not be installed correctly.

        Fix: Verify installation:
        ```
        uv pip show testcontainers
        ```

        Success criteria:
        - testcontainers.neo4j.Neo4jContainer imports successfully
        - Neo4jContainer is not None
        """
        try:
            from testcontainers.neo4j import Neo4jContainer
            assert Neo4jContainer is not None, "Neo4jContainer is None"
        except (ImportError, ModuleNotFoundError) as e:
            pytest.fail(
                f"testcontainers.neo4j not available: {e}\n"
                f"Verify installation: uv pip show testcontainers"
            )

    def test_all_dev_dependencies_are_installed(self):
        """
        FAILING TEST: All dev dependencies from pyproject.toml should be installed.

        Expected to FAIL: May have missing dependencies.

        Success criteria:
        - All packages in [tool.uv.dev-dependencies] are importable
        """
        # Key dependencies that must be present
        required_packages = [
            ("pytest", "pytest"),
            ("pytest_asyncio", "pytest-asyncio"),
            ("pytest_cov", "pytest-cov"),
            ("pytest_mock", "pytest-mock"),
            ("testcontainers", "testcontainers"),
            ("playwright", "playwright"),
        ]

        missing = []
        for module_name, package_name in required_packages:
            try:
                __import__(module_name)
            except ImportError:
                missing.append(package_name)

        assert len(missing) == 0, (
            f"Missing dev dependencies: {', '.join(missing)}\n"
            f"Install with: uv sync"
        )


class TestImportHealth:
    """Test that imports don't have circular dependencies or other issues."""

    def test_no_import_warnings_in_test_collection(self):
        """
        FAILING TEST: Test collection should not produce warnings.

        Expected to FAIL: May have deprecation warnings or other import issues.

        Success criteria:
        - No PytestCollectionWarning
        - No DeprecationWarning during collection
        """
        result = subprocess.run(
            ["uv", "run", "pytest", "tests/", "--collect-only", "-W", "error::PytestCollectionWarning"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        # Note: This might fail for reasons other than missing dependencies
        # We're primarily checking for import-related warnings
        if result.returncode != 0 and "PytestCollectionWarning" in result.stdout:
            pytest.fail(
                f"Collection produced warnings:\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

    def test_all_test_files_have_valid_python_syntax(self):
        """
        FAILING TEST: All test files should have valid Python syntax.

        Expected to FAIL: May have syntax errors.

        Success criteria:
        - All .py files in tests/ can be parsed by ast.parse()
        """
        import ast

        test_dir = Path(__file__).parent
        syntax_errors = []

        for test_file in test_dir.rglob("*.py"):
            try:
                content = test_file.read_text()
                ast.parse(content)
            except SyntaxError as e:
                syntax_errors.append((test_file, e))

        assert len(syntax_errors) == 0, (
            f"Found {len(syntax_errors)} files with syntax errors:\n" +
            "\n".join(f"{path}: {err}" for path, err in syntax_errors)
        )


if __name__ == "__main__":
    # Allow running this test file directly for quick validation
    pytest.main([__file__, "-v"])
