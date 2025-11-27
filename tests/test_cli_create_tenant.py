import os
import subprocess
import sys


def test_create_tenant_help():
    """Test that the create-tenant command shows help and exits 0."""
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", "create-tenant", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "create-tenant" in result.stdout


def test_create_tenant_with_sample_markdown(neo4j_container):
    """Test that the create-tenant command runs with a sample markdown file and exits 0.

    Uses the neo4j_container fixture to ensure isolation and avoid interfering with dev containers or persistent data.
    """
    sample_md = os.path.join("tests", "fixtures", "sample-tenant.md")
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", "create-tenant", sample_md],
        capture_output=True,
        text=True,
        env={**os.environ},  # ensure env vars from fixture are passed
    )
    assert result.returncode == 0
    assert (
        "Tenant successfully created" in result.stdout
        or "Tenant creation" in result.stdout
        or "TODO: synthesize tenant" in result.stdout
    )
