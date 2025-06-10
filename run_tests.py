"""
Test runner for Azure Tenant Grapher

This script runs all tests and provides comprehensive test coverage reporting.
"""

import argparse
import os
import subprocess  # nosec B404
import sys

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def run_tests(test_path=None, verbose=False, coverage=False) -> None:
    """
    Run tests with optional coverage reporting.

    Args:
        test_path: Specific test file or directory to run
        verbose: Enable verbose output
        coverage: Enable coverage reporting
    """
    # Base pytest command
    cmd = ["python", "-m", "pytest"]

    # Add test path or default to tests directory
    if test_path:
        cmd.append(test_path)
    else:
        cmd.append("tests/")

    # Add verbose flag
    if verbose:
        cmd.append("-v")

    # Add coverage flags
    if coverage:
        cmd.extend(
            [
                "--cov=src",
                "--cov-report=html:htmlcov",
                "--cov-report=term-missing",
                "--cov-branch",
            ]
        )

    # Add other useful flags
    cmd.extend(
        [
            "--tb=short",  # Shorter traceback format
            "--strict-markers",  # Strict marker checking
            "-ra",  # Show all test outcomes except passed
        ]
    )

    print(f"Running command: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=os.path.dirname(__file__))  # nosec B603


def check_dependencies() -> None:
    """Check if test dependencies are installed."""
    required_packages = ["pytest", "pytest-cov", "pytest-asyncio"]
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print(f"Missing test dependencies: {', '.join(missing_packages)}")
        print("Please install them with: pip install " + " ".join(missing_packages))
    # No return value


def main() -> None:
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run Azure Tenant Grapher tests")
    parser.add_argument(
        "test_path", nargs="?", help="Specific test file or directory to run"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "-c", "--coverage", action="store_true", help="Generate coverage report"
    )
    parser.add_argument(
        "--install-deps", action="store_true", help="Install test dependencies"
    )

    args = parser.parse_args()

    if args.install_deps:
        print("Installing test dependencies...")

        # Try uv first, then fall back to pip
        try:
            result = subprocess.run(  # nosec B603  # nosec B603
                [
                    "uv",
                    "add",
                    "--dev",
                    "pytest",
                    "pytest-cov",
                    "pytest-asyncio",
                    "pytest-mock",
                ]
            )
            if result.returncode == 0:
                print("✅ Test dependencies installed successfully with uv")
                return
        except FileNotFoundError:
            print("uv not found, trying pip...")

        # Fallback to pip
        result = subprocess.run(  # nosec B603  # nosec B603
            ["pip", "install", "pytest", "pytest-cov", "pytest-asyncio", "pytest-mock"]
        )
        if result.returncode == 0:
            print("✅ Test dependencies installed successfully with pip")
        else:
            print("❌ Failed to install test dependencies")
        return

    check_dependencies()

    print("🧪 Running Azure Tenant Grapher tests...")
    print("=" * 60)

    run_tests(args.test_path, args.verbose, args.coverage)
    # No return value


if __name__ == "__main__":
    main()
