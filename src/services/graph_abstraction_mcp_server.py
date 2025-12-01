"""MCP Server exposing graph abstraction operations to LLM agents.

Philosophy:
- Single responsibility: MCP interface layer only (no business logic)
- Ruthless simplicity: 4 tools, stateless, delegate to Neo4j session
- Zero-BS implementation: Every method works, no stubs or TODOs

Public API (the "studs"):
    GraphAbstractionMCPServer: Main MCP server class
    run: Server entry point

Dependencies:
- mcp>=1.9.4 (Model Context Protocol SDK)
- src.utils.session_manager.Neo4jSessionManager (Neo4j connection)

Usage:
    ```python
    from src.utils.session_manager import Neo4jSessionManager
    from src.services.graph_abstraction_mcp_server import GraphAbstractionMCPServer

    session_manager = Neo4jSessionManager(neo4j_config)
    session_manager.connect()

    server = GraphAbstractionMCPServer(session_manager)
    await server.run()
    ```

Provides 4 tools:
1. list_tenant_abstractions - List all abstractions for a tenant
2. get_abstraction_metadata - Get metadata for specific abstraction
3. get_abstraction_quality - Get quality metrics for abstraction
4. compare_abstractions - Compare two abstractions side by side

Issue #508: MCP Server and Visualization Export Integration
"""

import statistics
from typing import Any, Dict, List

import structlog
from mcp.server import Server
from mcp.types import TextContent, Tool

from src.utils.session_manager import Neo4jSessionManager

logger = structlog.get_logger(__name__)


class GraphAbstractionMCPServer:
    """MCP Server for graph abstraction operations.

    Exposes graph abstraction data and operations via Model Context Protocol.
    Designed to be consumed by LLM agents (Claude Desktop, Zed, etc.).
    """

    def __init__(self, session_manager: Neo4jSessionManager) -> None:
        """Initialize MCP server.

        Args:
            session_manager: Neo4j session manager for database operations
        """
        self.session_manager = session_manager
        self.server = Server("graph-abstraction-server")
        self._register_tools()

    def _register_tools(self) -> None:
        """Register MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available MCP tools."""
            return [
                Tool(
                    name="list_tenant_abstractions",
                    description="List all graph abstractions for a tenant",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tenant_id": {
                                "type": "string",
                                "description": "Azure tenant ID",
                            }
                        },
                        "required": ["tenant_id"],
                    },
                ),
                Tool(
                    name="get_abstraction_metadata",
                    description="Get metadata for a specific abstraction",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tenant_id": {
                                "type": "string",
                                "description": "Azure tenant ID",
                            }
                        },
                        "required": ["tenant_id"],
                    },
                ),
                Tool(
                    name="get_abstraction_quality",
                    description="Get quality metrics for an abstraction",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tenant_id": {
                                "type": "string",
                                "description": "Azure tenant ID",
                            }
                        },
                        "required": ["tenant_id"],
                    },
                ),
                Tool(
                    name="compare_abstractions",
                    description="Compare quality metrics between two abstractions",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tenant_id_1": {
                                "type": "string",
                                "description": "First tenant ID",
                            },
                            "tenant_id_2": {
                                "type": "string",
                                "description": "Second tenant ID",
                            },
                        },
                        "required": ["tenant_id_1", "tenant_id_2"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            if name == "list_tenant_abstractions":
                return await self._list_tenant_abstractions(arguments)
            elif name == "get_abstraction_metadata":
                return await self._get_abstraction_metadata(arguments)
            elif name == "get_abstraction_quality":
                return await self._get_abstraction_quality(arguments)
            elif name == "compare_abstractions":
                return await self._compare_abstractions(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

    async def _list_tenant_abstractions(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """List all abstractions for a tenant."""
        tenant_id = arguments["tenant_id"]

        with self.session_manager.session() as session:
            result = session.run(
                """
                MATCH (sample:Resource)-[:SAMPLE_OF]->(source:Resource)
                WHERE source.tenant_id = $tenant_id
                RETURN source.tenant_id as tenant_id,
                       count(DISTINCT sample) as sample_count,
                       count(DISTINCT source) as source_count,
                       collect(DISTINCT source.type)[0..10] as sample_types
                """,
                tenant_id=tenant_id,
            )

            data = result.single()
            if not data:
                return [
                    TextContent(
                        type="text",
                        text=f"No abstractions found for tenant {tenant_id}",
                    )
                ]

            return [
                TextContent(
                    type="text",
                    text=f"""Abstraction for tenant {tenant_id}:
- Sample size: {data["sample_count"]} nodes
- Source size: {data["source_count"]} nodes
- Sample ratio: {data["sample_count"] / max(1, data["source_count"]):.2%}
- Sample types: {", ".join(data["sample_types"][:5])}
""",
                )
            ]

    async def _get_abstraction_metadata(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Get detailed metadata for abstraction."""
        tenant_id = arguments["tenant_id"]

        with self.session_manager.session() as session:
            # Get type distribution
            result = session.run(
                """
                MATCH (sample:Resource)-[:SAMPLE_OF]->(source:Resource)
                WHERE source.tenant_id = $tenant_id
                RETURN source.type as type, count(sample) as count
                ORDER BY count DESC
                """,
                tenant_id=tenant_id,
            )

            type_dist = {record["type"]: record["count"] for record in result.data()}

            if not type_dist:
                return [
                    TextContent(
                        type="text",
                        text=f"No abstraction found for tenant {tenant_id}",
                    )
                ]

            # Format as readable text
            dist_text = "\n".join(
                [f"  {type_name}: {count}" for type_name, count in type_dist.items()]
            )

            return [
                TextContent(
                    type="text",
                    text=f"""Abstraction metadata for {tenant_id}:

Type distribution:
{dist_text}

Total types: {len(type_dist)}
Total samples: {sum(type_dist.values())}
""",
                )
            ]

    async def _get_abstraction_quality(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Get quality metrics for abstraction."""
        tenant_id = arguments["tenant_id"]

        with self.session_manager.session() as session:
            # Calculate quality metrics
            result = session.run(
                """
                MATCH (sample:Resource)-[:SAMPLE_OF]->(source:Resource)
                WHERE source.tenant_id = $tenant_id
                WITH source.type as type,
                     count(sample) as sample_count,
                     count(source) as source_count
                RETURN type,
                       sample_count,
                       source_count,
                       toFloat(sample_count) / source_count as ratio
                ORDER BY type
                """,
                tenant_id=tenant_id,
            )

            records = result.data()
            if not records:
                return [
                    TextContent(
                        type="text",
                        text=f"No abstraction found for tenant {tenant_id}",
                    )
                ]

            # Calculate distribution preservation quality (coefficient of variation)
            ratios = [r["ratio"] for r in records]
            avg_ratio = statistics.mean(ratios)
            std_ratio = statistics.stdev(ratios) if len(ratios) > 1 else 0
            cv = std_ratio / avg_ratio if avg_ratio > 0 else 0

            # Format metrics
            metrics_text = "\n".join(
                [
                    f"  {r['type']}: {r['sample_count']}/{r['source_count']} ({r['ratio']:.1%})"
                    for r in records[:10]  # Top 10 types
                ]
            )

            return [
                TextContent(
                    type="text",
                    text=f"""Abstraction quality for {tenant_id}:

Average sampling ratio: {avg_ratio:.2%}
Ratio std deviation: {std_ratio:.3f}
Coefficient of variation: {cv:.3f}
(Lower CV = better distribution preservation)

Sample ratios by type:
{metrics_text}
""",
                )
            ]

    async def _compare_abstractions(
        self, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """Compare two abstractions."""
        tenant_id_1 = arguments["tenant_id_1"]
        tenant_id_2 = arguments["tenant_id_2"]

        # Get quality metrics for both
        quality_1 = await self._get_abstraction_quality({"tenant_id": tenant_id_1})
        quality_2 = await self._get_abstraction_quality({"tenant_id": tenant_id_2})

        return [
            TextContent(
                type="text",
                text=f"""Comparison of abstractions:

=== Tenant 1: {tenant_id_1} ===
{quality_1[0].text}

=== Tenant 2: {tenant_id_2} ===
{quality_2[0].text}
""",
            )
        ]

    async def run(self) -> None:
        """Run the MCP server."""
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


__all__ = ["GraphAbstractionMCPServer"]
