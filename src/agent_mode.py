import asyncio
import logging
import sys
import itertools

async def _spinner(prefix: str):
    for ch in itertools.cycle("|/-\\"):
        print(f"\r{prefix} {ch}", end="", flush=True)
        try:
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            print("\r" + " " * (len(prefix) + 2) + "\r", end="", flush=True)
            break

from src.mcp_server import ensure_neo4j_running

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

    # Critical imports for agent mode
    try:
        from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams
        from autogen_agentchat.agents import AssistantAgent
        from src.llm_descriptions import LLMConfig
        # These imports are required for the dependencies to be available even if not directly used
        import tiktoken  # noqa: F401
        import openai  # noqa: F401
    except ModuleNotFoundError as error:
        print(
            f"❌ Failed to start agent mode: {error}\n"
            "Please ensure all required dependencies are installed: autogen_ext, autogen_agentchat, openai, tiktoken",
            file=sys.stderr,
        )
        sys.exit(1)

    # Set up MCP workbench - this will handle starting the MCP server
    print("🔧 Setting up MCP workbench...")
    try:
        workbench = McpWorkbench(server_params=StdioServerParams(command="uvx", args=["mcp-neo4j-cypher"]))
        print("✅ MCP workbench set up successfully")
    except Exception as e:
        print(f"❌ Failed to set up MCP workbench: {e}")
        sys.exit(1)

    # Use the same Azure OpenAI config and model client as the rest of the project
    llm_config = LLMConfig.from_env()
    if not llm_config.is_valid():
        print("❌ Azure OpenAI configuration is invalid. Please check your environment variables.", file=sys.stderr)
        sys.exit(1)
    from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
    model_client = AzureOpenAIChatCompletionClient(
        api_key=llm_config.api_key,
        azure_endpoint=llm_config.endpoint,
        api_version=llm_config.api_version,
        model=llm_config.model_chat,
    )

    # Define the assistant agent
    agent = AssistantAgent(
        name="GraphAssistant",
        system_message=SYSTEM_MESSAGE,
        workbench=workbench,
        model_client=model_client,
    )

    # Set up and run the console UI
    print("MCP Agent is ready", flush=True)
    print("🤖 Type your graph/tenant question (type 'x', 'exit', or 'quit' to exit):", flush=True)
    
    try:
        while True:
            try:
                user_input = await asyncio.to_thread(input, "> ")
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break
                
            user_input = user_input.strip()
            if not user_input:
                continue
                
            if user_input.lower() in {"exit", "quit", "x"}:
                print("Goodbye!")
                break
                
            # Send user input to the agent with a spinner
            spinner_task = asyncio.create_task(_spinner("🔄 Processing your question..."))
            try:
                response_received = False
                response_parts = []
                
                async for message in agent.run_stream(task=user_input):
                    # Cancel spinner on first response
                    if not response_received:
                        spinner_task.cancel()
                        try:
                            await spinner_task
                        except asyncio.CancelledError:
                            pass
                        print("")  # Clear the spinner line
                        response_received = True
                    
                    # Extract and collect response content
                    content = None
                    if hasattr(message, 'chat_message') and hasattr(message.chat_message, 'content'):
                        content = message.chat_message.content
                    elif hasattr(message, 'content'):
                        content = message.content
                    elif hasattr(message, 'text'):
                        content = message.text
                    
                    # Handle content that might be a list or string
                    if content:
                        if isinstance(content, list):
                            # If content is a list, join the parts
                            content_str = ' '.join(str(part) for part in content if part)
                        else:
                            content_str = str(content)
                        
                        if content_str and content_str.strip():
                            response_parts.append(content_str.strip())
                
                # Cancel spinner if still running
                if not response_received:
                    spinner_task.cancel()
                    try:
                        await spinner_task
                    except asyncio.CancelledError:
                        pass
                
                # Print the complete response
                if response_parts:
                    full_response = "\n".join(response_parts)
                    print(f"\nAssistant: {full_response}")
                else:
                    print("\n❌ No response received from agent. Check your Azure OpenAI configuration and MCP server.")
                    
            except Exception as e:
                # Cancel spinner on error
                spinner_task.cancel()
                try:
                    await spinner_task
                except asyncio.CancelledError:
                    pass
                print(f"\n❌ Error processing request: {e}")
                
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        try:
            # Clean up the workbench
            if 'workbench' in locals():
                await workbench.close()
        except:
            pass  # Ignore cleanup errors
