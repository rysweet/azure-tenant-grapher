"""
Basic integration tests for MCP server functionality.

These tests use the already running Neo4j container and test MCP server operations.
"""

import asyncio
import json
import os
from typing import Any, Dict

import pytest
from dotenv import load_dotenv


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
        # Step 1: Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        init_response = await self.send_request(init_request)

        # Step 2: Send initialized notification (no response expected)
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        if not self.process.stdin:
            raise RuntimeError("Process stdin not available")
        notification_json = json.dumps(initialized_notification) + "\n"
        self.process.stdin.write(notification_json.encode())
        await self.process.stdin.drain()

        return init_response

    async def list_tools(self) -> Dict[str, Any]:
        """List available tools from MCP server."""
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        return await self.send_request(request)

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any], request_id: int = 3
    ) -> Dict[str, Any]:
        """Call a specific tool on the MCP server."""
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        return await self.send_request(request)

    async def initialize_and_setup(self) -> None:
        """Initialize the MCP session - call this before using tools."""
        init_response = await self.initialize()
        if "error" in init_response:
            raise RuntimeError(
                f"Failed to initialize MCP session: {init_response['error']}"
            )

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
async def mcp_server_process():
    """Start an MCP server process for testing using environment variables."""
    # Load environment variables from .env like the CLI does
    load_dotenv()

    # Ensure we're using the correct Neo4j connection settings
    neo4j_uri = os.environ.get("NEO4J_URI", "bolt://localhost:8768")
    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "azure-grapher-2024")

    # Set environment variables for the MCP server process
    env = os.environ.copy()
    env.update(
        {
            "NEO4J_URI": neo4j_uri,
            "NEO4J_USER": neo4j_user,
            "NEO4J_PASSWORD": neo4j_password,
        }
    )

    process = None
    try:
        # Launch MCP server with environment variables
        process = await asyncio.create_subprocess_exec(
            "uvx",
            "mcp-neo4j-cypher",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

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


@pytest.mark.asyncio
async def test_mcp_server_startup_and_tools(mcp_server_process: MCPServerTester):
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
async def test_mcp_get_schema_tool(mcp_server_process: MCPServerTester):
    """Test the get_neo4j_schema tool."""
    tester = mcp_server_process

    # Initialize first
    await tester.initialize_and_setup()

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


@pytest.mark.asyncio
async def test_mcp_read_cypher_tool(mcp_server_process: MCPServerTester):
    """Test the read_neo4j_cypher tool with a simple query."""
    tester = mcp_server_process

    # Initialize first
    await tester.initialize_and_setup()

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
async def test_mcp_multi_step_workflow(mcp_server_process: MCPServerTester):
    """Test multiple tool calls in sequence - the key workflow for agent mode."""
    tester = mcp_server_process

    # Initialize first
    await tester.initialize_and_setup()

    # Step 1: Get schema (simulating what an agent would do first)
    schema_response = await tester.call_tool("get_neo4j_schema", {}, request_id=10)
    assert "result" in schema_response

    # Step 2: Query for storage resources specifically (simulating agent answering a question)
    storage_query = """
    MATCH (r:Resource)
    WHERE toLower(r.type) CONTAINS 'storage'
    RETURN count(r) as storage_count
    """
    storage_response = await tester.call_tool(
        "read_neo4j_cypher", {"query": storage_query}, request_id=11
    )
    assert "result" in storage_response

    # Parse the response to verify we get a numeric result
    content = storage_response["result"]["content"]
    assert isinstance(content, list)
    assert len(content) > 0

    result_text = content[0]["text"]
    result_data = json.loads(result_text)

    assert isinstance(result_data, list)
    if result_data:
        assert "storage_count" in result_data[0]
        assert isinstance(result_data[0]["storage_count"], int)

    print(
        f"✅ Multi-step workflow succeeded: Found {result_data[0]['storage_count'] if result_data else 0} storage resources"
    )


@pytest.mark.asyncio
async def test_mcp_connection_test(mcp_server_process: MCPServerTester):
    """Test that MCP server can successfully connect to Neo4j using environment variables."""
    tester = mcp_server_process

    # Initialize first
    await tester.initialize_and_setup()

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

    print("✅ MCP server successfully connected to Neo4j using environment variables")
