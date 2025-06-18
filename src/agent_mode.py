import asyncio
import logging
import sys

from src.mcp_server import ensure_neo4j_running, launch_mcp_server

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE = (
    "You are a graph/tenant assistant. "
    "You must only answer questions about the Azure graph or tenant data. "
    "If asked anything unrelated, politely refuse."
)

async def run_agent_mode():
    """
    Ensure Neo4j and MCP server are running, then start AutoGen MCP agent chat loop.
    Follows the official AutoGen MCP agent example.
    """
    try:
        await ensure_neo4j_running()
    except Exception as e:
        logger.error(f"Failed to start Neo4j: {e}")
        print(f"❌ Failed to start Neo4j: {e}", file=sys.stderr)
        sys.exit(1)

    # Start MCP server as subprocess (stdio, attached)
    mcp_proc = await launch_mcp_server()
    await asyncio.sleep(2)  # Give MCP server a moment to start

    from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.ui import Console
    from autogen_ext.models.openai import OpenAIChatCompletionClient

    # Set up MCP workbench
    workbench = McpWorkbench(
        server=StdioServerParams(command="uvx", args=["mcp-neo4j-cypher"])
    )

    # Set up OpenAI model client (uses environment variables for API key/config)
    model_client = OpenAIChatCompletionClient()

    # Define the assistant agent
    agent = AssistantAgent(
        name="GraphAssistant",
        system_message=SYSTEM_MESSAGE,
        workbench=workbench,
        client=model_client,
    )

    # Set up the console UI
    console = Console(agent)

    print("🤖 MCP Agent is ready. Type your graph/tenant question (Ctrl+C to exit):")
    try:
        await console.run_async()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting agent mode.")
    finally:
        mcp_proc.terminate()
        await mcp_proc.wait()
