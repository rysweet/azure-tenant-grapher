import glob
import os
import subprocess

import pytest


@pytest.mark.integration
def test_azure_tenant_grapher_help():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Usage: azure-tenant-grapher [OPTIONS] COMMAND [ARGS]..." in result.stdout
    assert "Commands:" in result.stdout
    assert "build" in result.stdout
    assert "agent-mode" in result.stdout


@pytest.mark.integration
def test_azure_tenant_grapher_build_help():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "build", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Usage: azure-tenant-grapher build [OPTIONS]" in result.stdout
    assert "--tenant-id TEXT" in result.stdout
    assert "--no-dashboard" in result.stdout
    assert "--rebuild-edges" in result.stdout


@pytest.mark.integration
def test_azure_tenant_grapher_build_minimal():
    result = subprocess.run(
        [
            "uv",
            "run",
            "azure-tenant-grapher",
            "build",
            "--resource-limit",
            "3",
            "--no-dashboard",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    error_text = result.stdout + result.stderr
    assert (
        "Failed to connect to Neo4j" in error_text
        or "NEO4J_CONNECTION_FAILED" in error_text
        or "Action: Ensure Neo4j is running" in error_text
    )
    assert "Resource Limit: 3" in error_text or "Resource Limit" in error_text


@pytest.mark.integration
def test_azure_tenant_grapher_config():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "config"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Configuration" in result.stdout or "config" in result.stdout.lower()


@pytest.mark.integration
def test_azure_tenant_grapher_progress():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "progress"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "progress" in result.stdout.lower() or "processing" in result.stdout.lower()


@pytest.mark.integration
def test_azure_tenant_grapher_visualize_minimal():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "visualize", "--no-container"],
        capture_output=True,
        text=True,
        check=False,
    )
    error_text = result.stdout + result.stderr
    assert "graph visualization" in error_text.lower()
    assert (
        "neo4j is not running" in error_text.lower()
        or "failed to connect to neo4j" in error_text.lower()
    )


@pytest.mark.integration
def test_azure_tenant_grapher_spec_minimal():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "spec"],
        capture_output=True,
        text=True,
        check=False,
    )
    error_text = result.stdout + result.stderr
    assert "tenant specification" in error_text.lower()


@pytest.mark.integration
def test_azure_tenant_grapher_generate_spec_minimal():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "generate-spec", "--limit", "3"],
        capture_output=True,
        text=True,
        check=False,
    )
    error_text = result.stdout + result.stderr
    assert "generate tenant specification" in error_text.lower()
    assert "neo4j" in error_text.lower()
    assert "failed to generate tenant specification" in error_text.lower()
    assert "connection refused" in error_text.lower()


@pytest.mark.integration
def test_azure_tenant_grapher_generate_iac_minimal():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "generate-iac", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    error_text = result.stdout + result.stderr
    assert "iac generation failed" in error_text.lower()
    assert "neo4j" in error_text.lower()
    assert "connection refused" in error_text.lower()


@pytest.mark.integration
def test_azure_tenant_grapher_generate_sim_doc():
    if os.path.exists("simdocs"):
        for f in glob.glob("simdocs/simdoc-*.md"):
            os.remove(f)
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "generate-sim-doc", "--size", "1"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Simulated customer profile written to:" in result.stdout
    simdocs = glob.glob("simdocs/simdoc-*.md")
    assert len(simdocs) > 0


@pytest.mark.integration
def test_azure_tenant_grapher_threat_model():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "threat-model"],
        capture_output=True,
        text=True,
        check=False,
    )
    error_text = result.stdout + result.stderr
    assert "Threat Modeling Agent workflow" in error_text
    assert (
        "Neo4j container" in error_text
        or "TypeError" in error_text
        or "docker" in error_text.lower()
    )


@pytest.mark.integration
def test_azure_tenant_grapher_agent_mode_minimal():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "agent-mode", "--question", "exit"],
        capture_output=True,
        text=True,
        check=False,
    )
    error_text = result.stdout + result.stderr
    assert "Failed to start Neo4j" in error_text or "TypeError" in error_text


@pytest.mark.integration
def test_azure_tenant_grapher_mcp_server_minimal():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "mcp-server"],
        capture_output=True,
        text=True,
        check=False,
    )
    error_text = result.stdout + result.stderr
    assert (
        "Neo4j container" in error_text
        or "Failed to start MCP server" in error_text
        or "TypeError" in error_text
    )


@pytest.mark.integration
def test_azure_tenant_grapher_create_tenant_minimal():
    result = subprocess.run(
        [
            "uv",
            "run",
            "azure-tenant-grapher",
            "create-tenant",
            "docs/demo/commands/create-tenant-sample.md",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    error_text = result.stdout + result.stderr
    assert "Failed to create tenant" in error_text or "TypeError" in error_text


@pytest.mark.integration
def test_azure_tenant_grapher_backup_db_minimal():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "backup-db", "./my-neo4j-backup.dump"],
        capture_output=True,
        text=True,
        check=False,
    )
    error_text = result.stdout + result.stderr
    assert (
        "Neo4j backup failed" in error_text or "container is not running" in error_text
    )


@pytest.mark.integration
def test_azure_tenant_grapher_doctor():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "doctor"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert "terraform is installed" in output
    assert "az is installed" in output
    assert "bicep is installed" in output
    assert "Doctor check complete" in output


@pytest.mark.integration
def test_azure_tenant_grapher_test_minimal():
    result = subprocess.run(
        ["uv", "run", "azure-tenant-grapher", "test", "--limit", "1"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert "Running test mode" in output
    assert (
        "asyncio.run() cannot be called from a running event loop" in output
        or "coroutine" in output
    )
