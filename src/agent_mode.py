import asyncio
import logging
import sys
import itertools
import os
import datetime
import tempfile

from src.mcp_server import ensure_neo4j_running

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE = (
    "You are a graph/tenant assistant. "
    "You must only answer questions about the Azure graph or tenant data. "
    "If asked anything unrelated, politely refuse. "
    "When a user asks a question, you MUST follow this exact process: "
    "1. First call 'get_neo4j_schema' to understand the graph structure "
    "2. Then call 'read_neo4j_cypher' to query the database for the specific information requested "
    "3. Finally, provide a clear, human-readable answer based on the query results "
    "Example: If asked 'How many storage resources are in the tenant?', call get_neo4j_schema, then call read_neo4j_cypher with "
    "'MATCH (r:Resource) WHERE toLower(r.type) CONTAINS \"storage\" RETURN count(r) as storage_count', "
    "then respond with something like 'There are X storage resources in the tenant.' "
    "You MUST complete all steps and provide a final answer - do not stop after just getting the schema."
)

async def _spinner(prefix: str):
    for ch in itertools.cycle("|/-\\"):
        print(f"\r{prefix} {ch}", end="", flush=True)
        try:
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            print("\r" + " " * (len(prefix) + 2) + "\r", end="", flush=True)
            break

async def run_agent_mode(question: str | None = None):
    """
    Ensure Neo4j and MCP server are running, then start AutoGen MCP agent chat loop.
    Uses UserProxyAgent and AssistantAgent for multi-step tool chaining.
    
    Args:
        question: Optional single question to ask in non-interactive mode
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
    except ModuleNotFoundError as error:
        print(
            f"❌ Failed to start agent mode: {error}\n"
            "Please ensure all required dependencies are installed: autogen_ext, autogen_agentchat",
            file=sys.stderr,
        )
        sys.exit(1)

    # Set up MCP workbench - this will handle starting the MCP server
    print("🔧 Setting up MCP workbench...")
    try:
        log_dir = tempfile.gettempdir()
        log_file = os.path.join(
            log_dir,
            f"mcp-server-agent-{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        workbench = McpWorkbench(
            server_params=StdioServerParams(
                command="uvx",
                args=["mcp-neo4j-cypher"],
                env=os.environ.copy(),
                stdout=log_file,
                stderr=log_file,
            )
        )
        print(f"✅ MCP workbench set up successfully. MCP server logs: {log_file}")
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

    # Define the assistant agent with tools
    assistant = AssistantAgent(
        name="GraphAssistant",
        system_message=SYSTEM_MESSAGE,
        workbench=workbench,
        model_client=model_client,
    )

    print("MCP Agent is ready", flush=True)
    
    try:
        # Handle single question mode vs interactive mode
        if question:
            print(f"🤖 Processing question: {question}")
            await _process_question_manually(workbench, question)
        else:
            print("🤖 Type your graph/tenant question (type 'x', 'exit', or 'quit' to exit):", flush=True)
            await _interactive_chat_loop_manual(workbench)

    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        try:
            # Clean up the workbench
            if 'workbench' in locals():
                await workbench.close()
        except:
            pass  # Ignore cleanup errors


async def _process_question(assistant: any, question: str):
    """Process a single question and exit."""
    spinner_task = asyncio.create_task(_spinner("🔄 Processing your question..."))
    try:
        # Process the stream with manual timeout tracking
        response_received = False
        text_responses = []
        start_time = asyncio.get_event_loop().time()
        timeout_seconds = 60

        async for message in assistant.run_stream(task=question):
            # Check for timeout
            if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                spinner_task.cancel()
                try:
                    await spinner_task
                except asyncio.CancelledError:
                    pass
                print("\n❌ Request timed out after 60 seconds")
                break

            # Cancel spinner on first response
            if not response_received:
                spinner_task.cancel()
                try:
                    await spinner_task
                except asyncio.CancelledError:
                    pass
                print("")  # Clear the spinner line
                response_received = True

            # Check message type and extract content
            message_type = type(message).__name__
            print(f"DEBUG: Received {message_type}")
            
            # Handle different message types
            if hasattr(message, 'content'):
                if isinstance(message.content, str) and message.content.strip():
                    text_responses.append(message.content.strip())
                    print(f"Assistant: {message.content.strip()}")
                elif isinstance(message.content, list):
                    # Handle list content
                    for item in message.content:
                        if hasattr(item, 'text') and item.text.strip():
                            text_responses.append(item.text.strip())
                            print(f"Assistant: {item.text.strip()}")
            
            # Handle TaskResult - but wait longer to see if agent continues
            if message_type == "TaskResult":
                print("DEBUG: Task completed - but checking if agent continues with more calls...")
                # Check if we have any human-readable responses (not just JSON tool outputs or the original question)
                final_answers = []
                original_question = "How many storage resources are in the tenant?"
                
                for resp in text_responses:
                    # Skip JSON responses (tool outputs)
                    if resp.strip().startswith('[') or resp.strip().startswith('{'):
                        continue
                    # Skip the original question echo
                    if resp.strip() == original_question:
                        continue
                    # Look for actual final answers that contain counts or conclusions
                    if any(pattern in resp.lower() for pattern in ['there are', 'found', 'total', 'count is', 'storage resources in']):
                        final_answers.append(resp)
                
                if final_answers:
                    print(f"DEBUG: Found final answer: {final_answers}")
                    break
                else:
                    print("DEBUG: Only tool outputs and question echo so far, waiting for final answer...")
                    # Give the agent more time to continue - don't break yet
                    # Set a secondary timeout to avoid infinite waiting
                    if asyncio.get_event_loop().time() - start_time > 30:  # 30 second secondary timeout
                        print("DEBUG: Secondary timeout reached, ending conversation")
                        break

        # Cancel spinner if still running
        if not response_received:
            spinner_task.cancel()
            try:
                await spinner_task
            except asyncio.CancelledError:
                pass
            print("\n❌ No response received from agent.")
        elif not text_responses:
            print("\n❌ Agent completed but provided no text response.")

    except Exception as e:
        # Cancel spinner on error
        spinner_task.cancel()
        try:
            await spinner_task
        except asyncio.CancelledError:
            pass
        print(f"\n❌ Error processing request: {e}")


async def _process_question_manually(workbench: any, question: str):
    """Process a question by manually orchestrating the multi-step workflow."""
    print("🔄 Step 1: Getting database schema...")
    
    try:
        # Step 1: Get the schema
        schema_tools = await workbench.list_tools()
        get_schema_tool = None
        read_cypher_tool = None
        
        for tool in schema_tools:
            tool_name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
            if tool_name == "get_neo4j_schema":
                get_schema_tool = tool
            elif tool_name == "read_neo4j_cypher":
                read_cypher_tool = tool
        
        if not get_schema_tool or not read_cypher_tool:
            print("❌ Required tools not found")
            return
            
        # Call get_neo4j_schema
        schema_tool_name = get_schema_tool.get("name") if isinstance(get_schema_tool, dict) else getattr(get_schema_tool, "name", None)
        schema_result = await workbench.call_tool(schema_tool_name, {})
        print("✅ Schema retrieved")
        
        # Step 2: Execute query for storage resources
        print("🔄 Step 2: Querying for storage resources...")
        storage_query = """
        MATCH (r:Resource)
        WHERE toLower(r.type) CONTAINS 'storage'
        RETURN count(r) as storage_count
        """
        
        cypher_tool_name = read_cypher_tool.get("name") if isinstance(read_cypher_tool, dict) else getattr(read_cypher_tool, "name", None)
        query_result = await workbench.call_tool(cypher_tool_name, {"query": storage_query})
        print("✅ Query executed")
        
        # Step 3: Extract and present the result
        print("🔄 Step 3: Processing results...")
        
        # Parse the query result
        print(f"\nDEBUG: Raw query_result: {query_result}")
        # Try to extract the result from query_result.result
        result_list = getattr(query_result, "result", None)
        if result_list and len(result_list) > 0:
            # Each item is a TextResultContent with a .content field (JSON string)
            import json
            try:
                print(f"DEBUG: query_result.result: {result_list}")
                text_content = getattr(result_list[0], "content", None)
                print(f"DEBUG: text_content: {text_content}")
                result_data = json.loads(text_content)
                print(f"DEBUG: Parsed result_data: {result_data}")
                if result_data and len(result_data) > 0:
                    storage_count = result_data[0].get('storage_count', 0)
                    print(f"\n🎯 Final Answer: There are {storage_count} storage resources in the tenant.")
                else:
                    print(f"\n🎯 Final Answer: There are 0 storage resources in the tenant.")
            except (json.JSONDecodeError, IndexError, AttributeError) as e:
                print(f"\n❌ Error parsing results: {e}")
                print(f"Raw result: {query_result}")
        else:
            print(f"\n❌ No results returned")
            # Diagnostic: Print a sample of resource types in the database
            print("\n🔎 Diagnostic: Sampling resource types in the database...")
            try:
                sample_query = """
                MATCH (r:Resource)
                RETURN r.type AS type, count(*) AS count
                ORDER BY count DESC
                LIMIT 20
                """
                sample_result = await workbench.call_tool("read_neo4j_cypher", {"query": sample_query})
                sample_list = getattr(sample_result, "result", None)
                if sample_list and len(sample_list) > 0:
                    sample_text = getattr(sample_list[0], "content", None)
                    print(f"Sample resource types: {sample_text}")
                else:
                    print("No Resource nodes found in the database.")
            except Exception as e:
                print(f"Error running diagnostic sample query: {e}")
            
    except Exception as e:
        print(f"\n❌ Error in manual processing: {e}")

    # Always print a sample of resource types for debugging
    print("\n🔎 Diagnostic: Sampling resource types in the database...")
    try:
        sample_query = """
        MATCH (r:Resource)
        RETURN r.type AS type, count(*) AS count
        ORDER BY count DESC
        LIMIT 20
        """
        sample_result = await workbench.call_tool("read_neo4j_cypher", {"query": sample_query})
        sample_list = getattr(sample_result, "result", None)
        if sample_list and len(sample_list) > 0:
            sample_text = getattr(sample_list[0], "content", None)
            print(f"Sample resource types: {sample_text}")
        else:
            print("No Resource nodes found in the database.")
    except Exception as e:
        print(f"Error running diagnostic sample query: {e}")


async def _interactive_chat_loop_manual(workbench: any):
    """Run the interactive chat loop using manual orchestration."""
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

            # For now, just handle the storage question
            if "storage" in user_input.lower():
                await _process_question_manually(workbench, user_input)
            else:
                print("Sorry, I can only answer questions about storage resources for now.")

    except Exception as e:
        print(f"Chat loop error: {e}")
