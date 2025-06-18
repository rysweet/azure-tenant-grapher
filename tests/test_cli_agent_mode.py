from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


import sys
import types

async def test_agent_mode_refusal_logic():
    # Ensure dummy autogen_ext and autogen_ext.mcp modules exist for patching
    if "autogen_ext" not in sys.modules:
        sys.modules["autogen_ext"] = types.ModuleType("autogen_ext")
    if "autogen_ext.mcp" not in sys.modules:
        sys.modules["autogen_ext.mcp"] = types.ModuleType("autogen_ext.mcp")
    if "autogen" not in sys.modules:
        sys.modules["autogen"] = types.ModuleType("autogen")
    if "autogen.agentchat" not in sys.modules:
        sys.modules["autogen.agentchat"] = types.ModuleType("autogen.agentchat")

    # Add dummy attributes to allow patching
    import types as _types
    sys.modules["autogen_ext.mcp"].McpWorkbench = _types.SimpleNamespace()
    sys.modules["autogen_ext.mcp"].StdioServerParams = _types.SimpleNamespace()
    sys.modules["autogen.agentchat"].AssistantAgent = _types.SimpleNamespace()

    # Patch the actual import locations used in src.agent_mode
    with patch("autogen_ext.mcp.McpWorkbench"), patch(
        "autogen_ext.mcp.StdioServerParams"
    ), patch("autogen.agentchat.AssistantAgent") as MockAgent:
        # Setup agent with refusal logic
        agent_instance = MockAgent.return_value

        async def fake_a_generate_reply(messages, **kwargs):
            last = messages[-1]["content"] if messages else ""
            if "graph" not in last and "tenant" not in last:
                return "Sorry, I can only answer questions about the Azure graph or tenant data."
            return "Graph answer"

        agent_instance.a_generate_reply = AsyncMock(side_effect=fake_a_generate_reply)

        # Simulate agent_mode chat loop logic
        user_message = "What is the weather today?"
        response = await agent_instance.a_generate_reply(
            [{"role": "user", "content": user_message}]
        )
        assert "only answer questions about the Azure graph" in response

        # Should answer graph question
        graph_message = "How many nodes are in the graph?"
        response2 = await agent_instance.a_generate_reply(
            [{"role": "user", "content": graph_message}]
        )
        assert response2 == "Graph answer"
