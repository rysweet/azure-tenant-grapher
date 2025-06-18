import sys
import subprocess
import time
import pytest

pytestmark = pytest.mark.asyncio

def has_autogen_ext_and_openai():
    try:
        import autogen_ext.tools.mcp
        import autogen_ext.models.openai
        import autogen_agentchat.agents
        import autogen_agentchat.ui
        import openai
        return True
    except ImportError:
        return False

@pytest.mark.skipif(
    not has_autogen_ext_and_openai(), reason="autogen_ext or openai not installed"
)
def test_agent_mode_cli_graph_and_non_graph(tmp_path):
    """
    Launch agent-mode in a subprocess, send graph and non-graph questions,
    and assert correct responses.
    """
    import os

    # Start the agent-mode subprocess
    proc = subprocess.Popen(
        [sys.executable, "scripts/cli.py", "agent-mode"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    try:
        # Wait for agent to be ready
        ready = False
        for _ in range(30):
            line = proc.stdout.readline()
            if "MCP Agent is ready" in line:
                ready = True
                break
        assert ready, "Agent did not start in time"

        # Send a non-graph question
        proc.stdin.write("What is the weather today?\n")
        proc.stdin.flush()
        time.sleep(2)
        output = ""
        for _ in range(10):
            line = proc.stdout.readline()
            output += line
            if "Assistant:" in line:
                break
        assert (
            "only answer questions about the Azure graph" in output
            or "refuse" in output.lower()
        ), f"Agent did not refuse non-graph question: {output}"

        # Send a graph question
        proc.stdin.write("How many nodes are in the graph?\n")
        proc.stdin.flush()
        time.sleep(2)
        output2 = ""
        for _ in range(10):
            line = proc.stdout.readline()
            output2 += line
            if "Assistant:" in line:
                break
        assert (
            "Sorry, I can only answer" not in output2
        ), f"Agent refused a valid graph question: {output2}"

        # Exit agent
        proc.stdin.write("exit\n")
        proc.stdin.flush()
        time.sleep(1)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

def is_autogen_agentchat_installed():
    try:
        import autogen_agentchat
        return True
    except ImportError:
        return False

@pytest.mark.skipif(
    not is_autogen_agentchat_installed(),
    reason="autogen_agentchat not installed at all; cannot test missing-dependency error",
)
def test_agent_mode_missing_autogen_agentchat(monkeypatch):
    """
    Launch agent-mode in a subprocess with autogen_agentchat missing,
    assert that the error message is printed and exit code is nonzero.
    """
    import os
    import tempfile
    import shutil

    # Create a temp empty directory to use as PYTHONPATH
    temp_dir = tempfile.mkdtemp()
    try:
        # Remove autogen_agentchat from sys.modules in subprocess by using a clean PYTHONPATH
        env = {**os.environ, "PYTHONPATH": temp_dir, "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen(
            [sys.executable, "scripts/cli.py", "agent-mode"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        out, err = proc.communicate(timeout=15)
        # The error message should be in stderr or stdout
        combined = (out or "") + (err or "")
        # Accept any missing required dependency for agent-mode, not just autogen_agentchat
        missing_dep_msgs = [
            "No module named 'autogen_agentchat'",
            "No module named 'tiktoken'",
            "No module named 'autogen_ext'",
            "No module named 'openai'",
        ]
        found_missing = any(msg in combined for msg in missing_dep_msgs)
        assert (
            "Failed to start agent mode" in combined and found_missing
        ), f"Did not find expected missing dependency error. Output:\n{combined}"
        assert proc.returncode != 0, f"Process exited with code {proc.returncode}, expected nonzero"
    finally:
        shutil.rmtree(temp_dir)
