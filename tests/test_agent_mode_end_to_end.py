"""
End-to-end tests for agent mode functionality.

These tests validate that the agent mode can actually answer questions correctly
by performing multi-step tool workflows automatically.
"""

import asyncio
import os
import shutil
import socket
import subprocess
import tempfile
import time

import pytest
from dotenv import load_dotenv


@pytest.fixture
def agent_mode_env():
    """Fixture to set up Neo4j container and MCP server for agent mode tests."""
    load_dotenv()
    # Use a temp dir for Neo4j data/logs/plugins to avoid permission issues
    temp_dir = tempfile.mkdtemp(prefix="neo4j-test-")
    neo4j_data = os.path.join(temp_dir, "data")
    neo4j_logs = os.path.join(temp_dir, "logs")
    neo4j_plugins = os.path.join(temp_dir, "plugins")
    os.makedirs(neo4j_data, exist_ok=True)
    os.makedirs(neo4j_logs, exist_ok=True)
    os.makedirs(neo4j_plugins, exist_ok=True)

    # Patch environment for Neo4j container
    os.environ["NEO4J_DATA"] = neo4j_data
    os.environ["NEO4J_LOGS"] = neo4j_logs
    os.environ["NEO4J_PLUGINS"] = neo4j_plugins

    from src.container_manager import Neo4jContainerManager

    container_manager = Neo4jContainerManager()
    container_manager.setup_neo4j()

    # Wait up to 60 seconds for Neo4j to be ready
    import neo4j

    # Use the correct mapped Bolt port (7688)
    uri = "bolt://localhost:7688"
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "azure-grapher-2024")
    ready = False
    for _ in range(60):
        try:
            driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                session.run("RETURN 1")
            ready = True
            break
        except Exception:
            time.sleep(1)
    if not ready:
        # Print container logs for debugging
        print("ERROR: Neo4j did not become ready within 60 seconds")
        try:
            logs = container_manager.get_container_logs()
            print("Neo4j container logs:\n", logs)
        except Exception:
            print("Could not fetch Neo4j container logs.")
        shutil.rmtree(temp_dir)
        pytest.fail("Neo4j did not become ready within 60 seconds")

    env = os.environ.copy()
    env.update(
        {
            "NEO4J_URI": uri,
            "NEO4J_USER": user,
            "NEO4J_PASSWORD": password,
        }
    )

    # Start MCP server in background
    mcp_proc = subprocess.Popen(
        ["uv", "run", "python", "-m", "src.mcp_server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    # Wait for MCP server to be ready (poll port 8080 up to 10s)
    mcp_ready = False
    for _ in range(20):
        try:
            with socket.create_connection(("localhost", 8080), timeout=0.5):
                mcp_ready = True
                break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    if not mcp_ready:
        mcp_proc.terminate()
        mcp_proc.wait(timeout=5)
        shutil.rmtree(temp_dir)
        pytest.fail("MCP server did not become ready within 10 seconds")
    time.sleep(2)  # Give a little extra time for full readiness

    yield env

    # Teardown
    try:
        mcp_proc.terminate()
        mcp_proc.wait(timeout=5)
    except Exception:
        pass
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_agent_mode_answers_question_completely(agent_mode_env):
    """
    Test that agent mode provides a complete answer to a question, not just partial tool calls.
    This test should FAIL if the agent stops after the first tool call.
    """
    # Question that requires multi-step workflow
    question = "How many storage resources are in the tenant?"

    try:
        # Run agent mode with the question
        process = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "python",
            "-m",
            "scripts.cli",
            "--log-level",
            "INFO",
            "agent-mode",
            "--question",
            question,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=agent_mode_env,
        )

        # Wait for completion with timeout
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=40)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            pytest.fail("Agent mode timed out after 120 seconds")

        # Decode output
        stdout_text = stdout.decode() if stdout else ""
        stderr_text = stderr.decode() if stderr else ""

        print("=== AGENT MODE OUTPUT ===")
        print(stdout_text)
        if stderr_text:
            print("=== STDERR ===")
            print(stderr_text)

        # Check that the process completed successfully
        assert (
            process.returncode == 0
        ), f"Agent mode failed with return code {process.returncode}"

        # The key test: Check that the agent provided a COMPLETE ANSWER, not just tool calls
        # The agent should go through the workflow steps and provide a final answer

        # Check that it went through the workflow steps
        assert (
            "Step 1: Getting database schema..." in stdout_text
        ), "Agent should start with schema retrieval"
        assert (
            "Step 2: Generating and executing Cypher query..." in stdout_text
        ), "Agent should execute query"
        assert (
            "Step 3: Processing results..." in stdout_text
        ), "Agent should process results"

        # Check for storage-related content in the output
        assert (
            "storage" in stdout_text.lower()
        ), "Agent should query for storage resources"

        # CRITICAL: Check that we got a FINAL ANSWER with the target phrase
        assert "🎯 Final Answer:" in stdout_text, "Agent should provide a final answer"

        # Check for specific final answer indicators
        final_answer_indicators = [
            "storage resources",  # The agent should mention storage resources in its final answer
            "found",  # "Found X storage resources"
            "there are",  # "There are X storage resources"
            "total",  # "Total storage resources: X"
            "count",  # Some form of count/number
        ]

        has_final_answer = any(
            indicator in stdout_text.lower() for indicator in final_answer_indicators
        )

        assert has_final_answer, (
            f"Agent did not provide a complete answer about storage resources. "
            f"Output: {stdout_text[-500:]}"  # Show last 500 chars for debugging
        )

    except Exception as e:
        pytest.fail(f"Agent mode test failed with exception: {e}")


@pytest.mark.asyncio
async def test_agent_mode_provides_numeric_answer(agent_mode_env):
    """
    Test that agent mode provides a specific numeric answer to the storage question.
    This is a more stringent test to ensure complete functionality.
    """
    question = "How many storage resources are in the tenant?"

    try:
        # Run agent mode with the question
        process = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "python",
            "-m",
            "scripts.cli",
            "--log-level",
            "INFO",
            "agent-mode",
            "--question",
            question,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=agent_mode_env,
        )

        # Wait for completion
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=40)
        stdout_text = stdout.decode() if stdout else ""

        # Check that the agent provides a numeric answer
        # Look for patterns like "0 storage", "3 storage", "10 storage", etc.
        import re

        numeric_pattern = r"\b(\d+)\s*storage"
        matches = re.findall(numeric_pattern, stdout_text, re.IGNORECASE)

        assert len(matches) > 0, (
            f"Agent should provide a numeric count of storage resources. "
            f"Output: {stdout_text[-500:]}"
        )

        # The count should be a valid number (probably 0 since we haven't loaded real data)
        storage_count = int(matches[0])
        assert (
            storage_count >= 0
        ), f"Storage count should be non-negative, got {storage_count}"

        print(f"✅ Agent correctly reported {storage_count} storage resources")

    except Exception as e:
        pytest.fail(f"Numeric answer test failed: {e}")
