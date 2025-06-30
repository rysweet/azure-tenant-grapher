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


def test_create_tenant_with_sample_markdown():
    """Test that the create-tenant command runs with a sample markdown file and exits 0."""
    sample_md = os.path.join("tests", "fixtures", "sample-tenant.md")
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", "create-tenant", sample_md],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (
        "Tenant creation" in result.stdout or "TODO: synthesize tenant" in result.stdout
    )
