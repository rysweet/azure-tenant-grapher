import os
import subprocess
import sys
import tempfile
import time

import pytest


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Subprocess signal handling is not reliable on Windows",
)
def test_real_dashboard_exit_subprocess():
    """
    Launch the CLI dashboard in a subprocess, simulate 'x' keypress via file,
    and assert that the process exits within 5 seconds.
    """
    # Path to the CLI script
    cli_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scripts", "cli.py")
    )
    assert os.path.exists(cli_path), f"CLI script not found: {cli_path}"

    # Create a temp file for simulated keypresses
    with tempfile.NamedTemporaryFile("w+", delete=False) as keyfile:
        keyfile_path = keyfile.name

    # Build the CLI command
    cmd = [
        sys.executable,
        cli_path,
        "build",
        "--tenant-id",
        "test-tenant",
        "--no-container",
        "--test-keypress-file",
        keyfile_path,
        "--resource-limit",
        "1",
        "--max-llm-threads",
        "1",
    ]

    # Start the CLI subprocess
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    try:
        # Wait longer for the dashboard and all threads to start
        time.sleep(5)
        # Simulate pressing "x"
        with open(keyfile_path, "w") as f:
            f.write("x\n")
        # Wait for process to exit (should be quick)
        try:
            outs, errs = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            outs, errs = proc.communicate()
            pytest.fail(
                f"CLI did not exit within 5 seconds after 'x' keypress.\nSTDOUT:\n{outs}\nSTDERR:\n{errs}"
            )
        # Check exit code
        assert (
            proc.returncode == 0
        ), f"CLI exited with nonzero code: {proc.returncode}\nSTDOUT:\n{outs}\nSTDERR:\n{errs}"
    finally:
        os.unlink(keyfile_path)
