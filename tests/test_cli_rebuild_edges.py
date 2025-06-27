import subprocess
import sys


def test_build_rebuild_edges_flag():
    """Test that the build CLI accepts --rebuild-edges and triggers the expected log output."""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/cli.py",
            "build",
            "--rebuild-edges",
            "--no-dashboard",
            "--resource-limit",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"CLI exited with code {result.returncode}. Output: {result.stdout} {result.stderr}"
    )
    assert (
        "re-evaluation of all relationships/edges" in result.stdout
        or "re-evaluation of all relationships/edges" in result.stderr
    ), f"Expected log output not found. Output: {result.stdout} {result.stderr}"
