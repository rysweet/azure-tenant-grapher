import asyncio
import logging
import sys

from src.mcp_server import ensure_neo4j_running, launch_mcp_server

logger = logging.getLogger(__name__)


async def run_agent_mode():
    """
    Ensure Neo4j and MCP server are running, then start AutoGen MCP agent chat loop.
    """
    import importlib
    # Check for autogen-ext[mcp] dependency before any autogen imports
    if importlib.util.find_spec("autogen_ext") is None:
        try:
            import click
            raise click.ClickException(
                "❌ autogen-ext is not installed. "
                "Install via:  pip install \"autogen-ext\""
            )
        except ImportError:
            raise SystemExit(
                "❌ autogen-ext is not installed. "
                "Install via:  pip install \"autogen-ext\""
            )
    try:
        await ensure_neo4j_running()
    except Exception as e:
        logger.error(f"Failed to start Neo4j: {e}")
        print(f"❌ Failed to start Neo4j: {e}", file=sys.stderr)
        sys.exit(1)

    # Start MCP server as subprocess (stdio, attached)
    mcp_proc = await launch_mcp_server()
    await asyncio.sleep(2)  # Give MCP server a moment to start

    try:
        # Import AutoGen MCP components
        from autogen.agentchat import AssistantAgent
        from autogen_ext.mcp import McpWorkbench, StdioServerParams
    except ImportError:
        print(
            "❌ autogen-ext is not installed. Please install it to use agent-mode.",
            file=sys.stderr,
        )
        mcp_proc.terminate()
        await mcp_proc.wait()
        sys.exit(1)

    # System message guard for graph/tenant questions only
    SYSTEM_MESSAGE = (
        "You are a graph/tenant assistant. "
        "You must only answer questions about the Azure graph or tenant data. "
        "If asked anything unrelated, politely refuse."
    )

    # Set up MCP workbench
    workbench = McpWorkbench(
        server=StdioServerParams(command="uvx", args=["mcp-neo4j-cypher"])
    )

    # Define refusal logic in the agent
    class GuardedAssistantAgent(AssistantAgent):
        def _should_refuse(self, message: str) -> bool:
            # Simple heuristic: refuse if not mentioning graph/tenant
            allowed_keywords = [
                "graph",
                "tenant",
                "node",
                "edge",
                "relationship",
                "cypher",
            ]
            return not any(kw in message.lower() for kw in allowed_keywords)

        async def a_generate_reply(self, messages, **kwargs):
            last = messages[-1]["content"] if messages else ""
            if self._should_refuse(last):
                return "Sorry, I can only answer questions about the Azure graph or tenant data."
            return await super().a_generate_reply(messages, **kwargs)

    agent = GuardedAssistantAgent(
        name="GraphAssistant",
        system_message=SYSTEM_MESSAGE,
        workbench=workbench,
    )

    print("🤖 MCP Agent is ready. Type your graph/tenant question (Ctrl+C to exit):")
    try:
        while True:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, input, "> "
            )
            if user_input.strip().lower() in {"exit", "quit"}:
                break
            response = await agent.a_generate_reply(
                [{"role": "user", "content": user_input}]
            )
            print(f"Assistant: {response}")
    except (KeyboardInterrupt, EOFError):
        print("\nExiting agent mode.")
    finally:
        mcp_proc.terminate()
        await mcp_proc.wait()
