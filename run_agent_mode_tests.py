#!/usr/bin/env python
"""
Test runner for Agent Mode E2E tests.

This script provides a convenient way to run the Agent Mode and MCP integration tests
with proper setup and teardown.
"""

import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import pytest
        import websockets
        print("✓ Required Python packages installed")
    except ImportError as e:
        print(f"✗ Missing required package: {e}")
        print("  Install with: pip install -r requirements-dev.txt")
        return False

    # Check for Neo4j
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=neo4j", "--format", "{{.Names}}"],
        capture_output=True,
        text=True
    )
    if "neo4j" in result.stdout:
        print("✓ Neo4j container is running")
    else:
        print("✗ Neo4j container not running")
        print("  Start with: docker-compose up -d neo4j")

    return True


def run_python_tests(args):
    """Run Python-based E2E tests."""
    cmd = ["python", "-m", "pytest", "tests/e2e/agent_mode/"]

    if args.verbose:
        cmd.append("-vv")
    else:
        cmd.append("-v")

    if args.test:
        cmd.append(f"-k={args.test}")

    if args.coverage:
        cmd.extend([
            "--cov=src.services.mcp_integration",
            "--cov-report=html",
            "--cov-report=term"
        ])

    if args.markers:
        cmd.append(f"-m={args.markers}")

    if args.junit:
        cmd.append(f"--junit-xml={args.junit}")

    if args.pdb:
        cmd.append("--pdb")

    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


def run_ui_tests(args):
    """Run Gadugi UI-based tests."""
    scenarios_path = Path("spa/agentic-testing/scenarios/agent-mode-workflows.yaml")

    if not scenarios_path.exists():
        print(f"✗ Scenarios file not found: {scenarios_path}")
        return 1

    os.chdir("spa/agentic-testing")

    # Install dependencies if needed
    if not Path("node_modules").exists():
        print("Installing npm dependencies...")
        subprocess.run(["npm", "install"], check=True)

    cmd = ["npm", "run", "test:scenario", "--", str(scenarios_path)]

    if args.scenario:
        cmd.extend(["--scenario", args.scenario])

    if args.headless:
        cmd.append("--headless")

    if args.video:
        cmd.append("--video")

    print(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd).returncode


async def start_mock_mcp_server(port=8080):
    """Start a simple mock MCP server for testing."""
    import websockets
    import json

    async def handle_connection(websocket, path):
        try:
            async for message in websocket:
                data = json.loads(message)

                # Simple echo response for testing
                response = {
                    "type": "response",
                    "id": data.get("id"),
                    "result": {"status": "ok", "echo": data}
                }

                await websocket.send(json.dumps(response))
        except websockets.exceptions.ConnectionClosed:
            pass

    server = await websockets.serve(handle_connection, "localhost", port)
    print(f"Mock MCP server started on ws://localhost:{port}")
    await server.wait_closed()


def main():
    parser = argparse.ArgumentParser(
        description="Run Agent Mode E2E tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests
  python run_agent_mode_tests.py

  # Run specific test
  python run_agent_mode_tests.py -t test_natural_language_query_processing

  # Run with coverage
  python run_agent_mode_tests.py --coverage

  # Run UI tests
  python run_agent_mode_tests.py --ui

  # Run specific UI scenario
  python run_agent_mode_tests.py --ui --scenario nlp-query-basic

  # Start mock MCP server
  python run_agent_mode_tests.py --mock-server
        """
    )

    parser.add_argument(
        "-t", "--test",
        help="Run specific test by name pattern"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    parser.add_argument(
        "-m", "--markers",
        help="Run tests with specific markers"
    )
    parser.add_argument(
        "--junit",
        help="Generate JUnit XML report"
    )
    parser.add_argument(
        "--pdb",
        action="store_true",
        help="Drop into debugger on failures"
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Run UI tests instead of Python tests"
    )
    parser.add_argument(
        "--scenario",
        help="Run specific UI test scenario"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run UI tests in headless mode"
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Record video of UI tests"
    )
    parser.add_argument(
        "--mock-server",
        action="store_true",
        help="Start mock MCP server for testing"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check dependencies, don't run tests"
    )

    args = parser.parse_args()

    # Check dependencies
    if not check_dependencies():
        if not args.check_only:
            print("\n⚠ Fix dependency issues before running tests")
            return 1
        return 0

    if args.check_only:
        print("\n✓ All dependencies satisfied")
        return 0

    # Start mock server if requested
    if args.mock_server:
        try:
            asyncio.run(start_mock_mcp_server())
        except KeyboardInterrupt:
            print("\nMock server stopped")
        return 0

    # Set environment variables for testing
    os.environ.setdefault("NEO4J_PASSWORD", "test_password")
    os.environ.setdefault("MCP_ENDPOINT", "ws://localhost:8080")
    os.environ.setdefault("AZURE_TENANT_ID", "test-tenant-1")
    os.environ.setdefault("AZURE_SUBSCRIPTION_ID", "test-sub-1")

    # Run appropriate tests
    if args.ui:
        return run_ui_tests(args)
    else:
        return run_python_tests(args)


if __name__ == "__main__":
    sys.exit(main())