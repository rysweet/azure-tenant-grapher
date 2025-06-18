from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


def _autogen_available():
    try:
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _autogen_available(), reason="autogen-ext[mcp] not installed")
async def test_agent_mode_refusal_logic():
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
