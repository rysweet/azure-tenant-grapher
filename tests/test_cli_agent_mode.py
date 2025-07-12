import logging
import os
import subprocess
import sys
import time
from typing import Any

import pytest


def print_cli_failure(proc: Any, stdout: str, stderr: str) -> None:
    print(f"Process exited with code {proc.returncode}")
    print("STDOUT:")
    print(stdout)
    print("STDERR:")
    print(stderr)


def test_agent_mode_requires_resources():
    """Test that agent-mode properly checks for required resources and fails if they're not available."""
    logger = logging.getLogger("test_cli_agent_mode")
    logging.basicConfig(level=logging.INFO)
    timeout = int(os.environ.get("AGENT_MODE_TIMEOUT_SECONDS", 60))
    logger.info(f"Starting agent-mode subprocess with timeout={timeout}s")
    start_time = time.time()
    proc = subprocess.Popen(
        [sys.executable, "scripts/cli.py", "agent-mode"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # Send immediate exit command
        stdout, stderr = proc.communicate(input="x\n", timeout=timeout)
        elapsed = time.time() - start_time
        logger.info(
            f"Subprocess completed in {elapsed:.2f}s with return code {proc.returncode}"
        )

        # The agent mode should either:
        # 1. Start successfully if all resources are available (Neo4j, Azure OpenAI config)
        # 2. Fail with specific error messages if resources are missing

        if proc.returncode == 0:
            # If successful, it should show readiness and exit cleanly
            assert "MCP Agent is ready" in stdout, (
                f"Agent started but didn't show ready message: {stdout}"
            )
            assert "Goodbye!" in stdout, f"Agent didn't exit cleanly: {stdout}"

        elif proc.returncode == 1:
            # If failed, it should show specific error messages about missing resources
            combined_output = stdout + stderr

            # Check for expected failure scenarios
            neo4j_failed = "Failed to start Neo4j" in combined_output
            config_invalid = "Azure OpenAI configuration is invalid" in combined_output
            deps_missing = (
                "Failed to start agent mode" in combined_output
                and "dependencies are installed" in combined_output
            )

            assert neo4j_failed or config_invalid or deps_missing, (
                f"Agent failed but didn't show expected error messages. "
                f"Return code: {proc.returncode}, "
                f"stdout: {stdout}, "
                f"stderr: {stderr}"
            )

            # If Neo4j failed, it should be because Docker isn't running or container issues
            if neo4j_failed:
                assert "Docker" in combined_output or "container" in combined_output, (
                    "Neo4j failure should mention Docker or container issues"
                )

        else:
            print_cli_failure(proc, stdout, stderr)
            pytest.fail(
                f"Unexpected return code {proc.returncode}. stdout: {stdout}, stderr: {stderr}"
            )

    except subprocess.TimeoutExpired:
        proc.kill()
        logger.error(f"Agent mode subprocess timed out after {timeout}s")
        pytest.fail(f"Agent mode did not respond within timeout ({timeout}s)")
    except Exception as e:
        proc.kill()
        logger.error(f"Agent mode test failed: {e}")
        pytest.fail(f"Agent mode test failed: {e}")


def test_agent_mode_cli_integration():
    """Test that agent-mode command is properly integrated into the CLI."""
    # Test that the CLI recognizes the agent-mode command
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Should show agent-mode in help output
    assert result.returncode == 0, f"CLI help failed: {result.stderr}"
    assert "agent-mode" in result.stdout, "agent-mode command not found in CLI help"


def test_agent_mode_dependency_validation():
    """Test that agent-mode validates dependencies correctly."""
    # This should run without error if dependencies are properly installed
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
sys.path.insert(0, '.')
try:
    from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams
    from autogen_agentchat.agents import AssistantAgent
    from src.llm_descriptions import LLMConfig
    import tiktoken
    import openai
    print("All dependencies available")
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)
        """,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        pytest.fail(f"Required agent-mode dependencies are missing: {result.stdout}")

    assert "All dependencies available" in result.stdout
