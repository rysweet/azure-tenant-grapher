"""
Integration tests for MCP server functionality.

These tests validate that the MCP server can start, respond to tool calls,
and properly interact with Neo4j database.
"""

import asyncio
import json
import os
from typing import Any, Dict, Tuple

import pytest
from dotenv import load_dotenv

from src.mcp_server import ensure_neo4j_running, launch_mcp_server


class MCPServerTester:
    """Helper class for testing MCP server functionality."""

    def __init__(self, process: asyncio.subprocess.Process):
        self.process = process

    async def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request to the MCP server and get response."""
        if not self.process.stdin:
            raise RuntimeError("Process stdin not available")

        # Send the request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()

        # Read the response
        if not self.process.stdout:
            raise RuntimeError("Process stdout not available")

        response_line = await self.process.stdout.readline()
        response_text = response_line.decode().strip()

        if not response_text:
            raise RuntimeError("No response received from MCP server")

        return json.loads(response_text)

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP session."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        return await self.send_request(request)

    async def list_tools(self) -> Dict[str, Any]:
        """List available tools from MCP server."""
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        return await self.send_request(request)

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any], request_id: int = 2
    ) -> Dict[str, Any]:
        """Call a specific tool on the MCP server."""
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        return await self.send_request(request)

    async def close(self):
        """Close the MCP server process."""
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()


@pytest.fixture
async def mcp_server_process(neo4j_container: Tuple[str, str, str]):
    """Start an MCP server process for testing using the same Neo4j setup as the CLI."""
    # neo4j_container is a session fixture from conftest.py that ensures Neo4j is running
    neo4j_uri, neo4j_user, neo4j_password = neo4j_container

    # Load environment variables from .env like the CLI does
    load_dotenv()

    # Set Neo4j environment variables to match what the CLI uses
    original_env = {}
    env_vars = {
        "NEO4J_URI": neo4j_uri,
        "NEO4J_USER": neo4j_user,
        "NEO4J_PASSWORD": neo4j_password,
    }

    # Backup and set environment variables
    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    process = None
    try:
        # Ensure Neo4j is ready (this will use the environment variables we just set)
        await ensure_neo4j_running()

        # Launch MCP server with pipes for communication
        process = await launch_mcp_server(attach_stdio=False)

        # Give the server time to start
        await asyncio.sleep(2)

        yield MCPServerTester(process)

    finally:
        # Clean up process
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

        # Restore original environment variables
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


@pytest.mark.asyncio
async def test_mcp_server_startup(mcp_server_process: MCPServerTester):
    """Test that MCP server starts up and responds to basic requests."""
    tester = mcp_server_process

    # First initialize the MCP session
    init_response = await tester.initialize()
    assert "result" in init_response
    assert "protocolVersion" in init_response["result"]

    # Test that we can list tools
    response = await tester.list_tools()

    assert "result" in response
    assert "tools" in response["result"]

    tools = response["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]

    # Check that expected tools are available
    expected_tools = ["get_neo4j_schema", "read_neo4j_cypher", "write_neo4j_cypher"]
    for expected_tool in expected_tools:
        assert (
            expected_tool in tool_names
        ), f"Tool {expected_tool} not found in {tool_names}"


@pytest.mark.asyncio
async def test_get_neo4j_schema_tool(mcp_server_process: MCPServerTester):
    """Test the get_neo4j_schema tool."""
    tester = mcp_server_process

    # Call the get_neo4j_schema tool
    response = await tester.call_tool("get_neo4j_schema", {})

    assert "result" in response
    assert "content" in response["result"]

    content = response["result"]["content"]
    assert isinstance(content, list)
    assert len(content) > 0

    # Content should be JSON with schema information
    first_item = content[0]
    assert "text" in first_item

    # Parse the schema JSON
    schema_text = first_item["text"]
    schema_data = json.loads(schema_text)

    assert isinstance(schema_data, list)
    # Should contain at least Resource and ResourceGroup labels
    labels = [item["label"] for item in schema_data]
    assert "Resource" in labels
    assert "ResourceGroup" in labels


@pytest.mark.asyncio
async def test_read_neo4j_cypher_tool(mcp_server_process: MCPServerTester):
    """Test the read_neo4j_cypher tool with a simple query."""
    tester = mcp_server_process

    # Call a simple Cypher query
    query = "MATCH (n) RETURN count(n) as node_count"
    response = await tester.call_tool("read_neo4j_cypher", {"query": query})

    assert "result" in response
    assert "content" in response["result"]

    content = response["result"]["content"]
    assert isinstance(content, list)
    assert len(content) > 0

    # Should return query results
    first_item = content[0]
    assert "text" in first_item

    # Parse the results
    result_text = first_item["text"]
    result_data = json.loads(result_text)

    assert isinstance(result_data, list)
    # Should have at least one result with node_count
    if result_data:
        assert "node_count" in result_data[0]
        assert isinstance(result_data[0]["node_count"], int)


@pytest.mark.asyncio
async def test_read_neo4j_cypher_tool_with_parameters(
    mcp_server_process: MCPServerTester,
):
    """Test the read_neo4j_cypher tool with parameterized query."""
    tester = mcp_server_process

    # Call a parameterized query
    query = "MATCH (r:Resource) WHERE r.type = $resource_type RETURN count(r) as count"
    params = {"resource_type": "Microsoft.Storage/storageAccounts"}
    response = await tester.call_tool(
        "read_neo4j_cypher", {"query": query, "params": params}
    )

    assert "result" in response
    assert "content" in response["result"]

    content = response["result"]["content"]
    assert isinstance(content, list)
    assert len(content) > 0


@pytest.mark.asyncio
async def test_write_neo4j_cypher_tool(mcp_server_process: MCPServerTester):
    """Test the write_neo4j_cypher tool with a simple write operation."""
    tester = mcp_server_process

    # Create a test node
    query = """
    CREATE (t:TestNode {
        name: $name,
        created_at: datetime(),
        test_id: $test_id
    })
    RETURN t.name as name, t.test_id as test_id
    """
    params = {"name": "mcp_test_node", "test_id": "test_123"}
    response = await tester.call_tool(
        "write_neo4j_cypher", {"query": query, "params": params}
    )

    assert "result" in response
    assert "content" in response["result"]

    content = response["result"]["content"]
    assert isinstance(content, list)
    assert len(content) > 0

    # Verify the node was created
    first_item = content[0]
    assert "text" in first_item
    result_data = json.loads(first_item["text"])

    assert isinstance(result_data, list)
    assert len(result_data) > 0
    assert result_data[0]["name"] == "mcp_test_node"
    assert result_data[0]["test_id"] == "test_123"

    # Clean up - delete the test node
    cleanup_query = "MATCH (t:TestNode {test_id: $test_id}) DELETE t"
    await tester.call_tool(
        "write_neo4j_cypher", {"query": cleanup_query, "params": params}
    )


@pytest.mark.asyncio
async def test_invalid_cypher_query_error_handling(mcp_server_process: MCPServerTester):
    """Test that invalid Cypher queries return proper errors."""
    tester = mcp_server_process

    # Send an invalid query
    invalid_query = "INVALID CYPHER SYNTAX"
    response = await tester.call_tool("read_neo4j_cypher", {"query": invalid_query})

    # Should return an error
    assert "error" in response or (
        "result" in response and "isError" in response["result"]
    )


@pytest.mark.asyncio
async def test_multi_step_tool_usage(mcp_server_process: MCPServerTester):
    """Test multiple tool calls in sequence to simulate agent behavior."""
    tester = mcp_server_process

    # Step 1: Get schema
    schema_response = await tester.call_tool("get_neo4j_schema", {}, request_id=10)
    assert "result" in schema_response

    # Step 2: Query for resource count
    count_query = "MATCH (r:Resource) RETURN count(r) as total_resources"
    count_response = await tester.call_tool(
        "read_neo4j_cypher", {"query": count_query}, request_id=11
    )
    assert "result" in count_response

    # Step 3: Query for storage resources specifically
    storage_query = """
    MATCH (r:Resource)
    WHERE toLower(r.type) CONTAINS 'storage'
    RETURN count(r) as storage_count
    """
    storage_response = await tester.call_tool(
        "read_neo4j_cypher", {"query": storage_query}, request_id=12
    )
    assert "result" in storage_response

    # All requests should succeed
    for response in [schema_response, count_response, storage_response]:
        assert "error" not in response


@pytest.mark.asyncio
async def test_concurrent_tool_calls(mcp_server_process: MCPServerTester):
    """Test that MCP server handles concurrent requests properly."""
    tester = mcp_server_process

    # Create multiple concurrent requests
    tasks = []
    for i in range(3):
        query = f"MATCH (n) RETURN count(n) as count_{i}"
        task = tester.call_tool(
            "read_neo4j_cypher", {"query": query}, request_id=20 + i
        )
        tasks.append(task)

    # Wait for all to complete
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # All should succeed (or at least not raise exceptions)
    for response in responses:
        assert not isinstance(response, Exception)
        if isinstance(response, dict):
            assert "result" in response or "error" in response


@pytest.mark.asyncio
async def test_mcp_server_connection_resilience(neo4j_container: Tuple[str, str, str]):
    """Test MCP server startup and shutdown cycle."""
    # Use the same Neo4j setup pattern as the main fixture
    neo4j_uri, neo4j_user, neo4j_password = neo4j_container

    # Load environment and set Neo4j vars
    load_dotenv()
    original_env = {}
    env_vars = {
        "NEO4J_URI": neo4j_uri,
        "NEO4J_USER": neo4j_user,
        "NEO4J_PASSWORD": neo4j_password,
    }

    for key, value in env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        # Ensure Neo4j is ready
        await ensure_neo4j_running()

        # Start server
        process = await launch_mcp_server(attach_stdio=False)
        tester = MCPServerTester(process)

        try:
            # Give time to start
            await asyncio.sleep(2)

            # Test basic functionality
            response = await tester.list_tools()
            assert "result" in response

            # Gracefully shut down
            await tester.close()

            # Verify process is terminated
            assert process.returncode is not None

        finally:
            # Ensure cleanup
            if process.returncode is None:
                process.kill()
                await process.wait()

    finally:
        # Restore environment variables
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value


@pytest.mark.asyncio
async def test_environment_variable_usage(mcp_server_process: MCPServerTester):
    """Test that MCP server uses correct environment variables for Neo4j connection."""
    tester = mcp_server_process

    # Test a query that would fail if connection is wrong
    query = "CALL db.ping() YIELD success RETURN success"
    response = await tester.call_tool("read_neo4j_cypher", {"query": query})

    # Should succeed if using correct environment variables
    assert "result" in response
    content = response["result"]["content"]
    assert len(content) > 0

    # Parse result
    result_data = json.loads(content[0]["text"])
    assert len(result_data) > 0
    assert result_data[0]["success"] is True
