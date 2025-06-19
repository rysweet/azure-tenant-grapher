import asyncio
import os
import pytest
from subprocess import PIPE, STDOUT

@pytest.mark.asyncio
async def test_agent_mode_storage_resource_count(
    neo4j_container, mcp_server_process
):
    """
    Integration test: agent mode should answer 'How many storage resources are in the tenant?'
    by chaining get_neo4j_schema and read_neo4j_cypher tool calls.
    This version uses the same robust dependency management as other integration tests.
    """
    # Use the environment variables from the fixtures
    neo4j_uri, neo4j_user, neo4j_password = neo4j_container
    env = os.environ.copy()
    env["NEO4J_URI"] = neo4j_uri
    env["NEO4J_USER"] = neo4j_user
    env["NEO4J_PASSWORD"] = neo4j_password

    # Start agent mode as a subprocess
    proc = await asyncio.create_subprocess_exec(
        "python",
        "-m",
        "scripts.cli",
        "agent-mode",
        stdin=PIPE,
        stdout=PIPE,
        stderr=STDOUT,
        env=env,
    )

    # Wait for the agent to be ready
    ready = False
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        decoded = line.decode()
        if "MCP Agent is ready" in decoded:
            ready = True
            break
    assert ready, "Agent did not start properly"

    # Send the test question
    proc.stdin.write(b"How many storage resources are in the tenant?\n")
    await proc.stdin.drain()

    # Read output for up to 30 seconds
    output = ""
    for _ in range(60):
        line = await proc.stdout.readline()
        if not line:
            break
        decoded = line.decode()
        output += decoded
        if "Assistant:" in decoded:
            break
        await asyncio.sleep(0.5)

    # Terminate the agent
    proc.terminate()
    await proc.wait()

    # Check that the output contains a numeric answer (not just the schema)
    assert "Assistant:" in output, "No assistant answer found"
    # Look for a number in the answer
    import re

    numbers = re.findall(r"\b\d+\b", output)
    assert numbers, f"No numeric answer found in output: {output}"

    print("Test output:", output)
