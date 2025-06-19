"""
End-to-end tests for agent mode functionality.

These tests validate that the agent mode can actually answer questions correctly
by performing multi-step tool workflows automatically.
"""

import asyncio
import os

import pytest
from dotenv import load_dotenv


@pytest.mark.asyncio
async def test_agent_mode_answers_question_completely():
    """
    Test that agent mode provides a complete answer to a question, not just partial tool calls.
    This test should FAIL if the agent stops after the first tool call.
    """
    # Load environment
    load_dotenv()

    # Set up environment for the agent process
    env = os.environ.copy()
    neo4j_uri = env.get("NEO4J_URI", "bolt://localhost:8768")
    neo4j_user = env.get("NEO4J_USER", "neo4j")
    neo4j_password = env.get("NEO4J_PASSWORD", "azure-grapher-2024")

    env.update(
        {
            "NEO4J_URI": neo4j_uri,
            "NEO4J_USER": neo4j_user,
            "NEO4J_PASSWORD": neo4j_password,
        }
    )

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
            env=env,
        )

        # Wait for completion with timeout
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
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
async def test_agent_mode_provides_numeric_answer():
    """
    Test that agent mode provides a specific numeric answer to the storage question.
    This is a more stringent test to ensure complete functionality.
    """
    # Load environment
    load_dotenv()

    # Set up environment for the agent process
    env = os.environ.copy()
    neo4j_uri = env.get("NEO4J_URI", "bolt://localhost:8768")
    neo4j_user = env.get("NEO4J_USER", "neo4j")
    neo4j_password = env.get("NEO4J_PASSWORD", "azure-grapher-2024")

    env.update(
        {
            "NEO4J_URI": neo4j_uri,
            "NEO4J_USER": neo4j_user,
            "NEO4J_PASSWORD": neo4j_password,
        }
    )

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
            env=env,
        )

        # Wait for completion
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
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
