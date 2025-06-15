import subprocess
import sys
import time


def test_cli_dashboard_log_level_and_exit(tmp_path):
    """Integration test: CLI dashboard log level and exit via keypresses."""
    # Prepare keypress file
    key_file = tmp_path / "keys.txt"
    with open(key_file, "w") as f:
        f.write("d")
        f.flush()
        time.sleep(1)
        f.write("w")
        f.flush()
        time.sleep(1)
        f.write("x")
        f.flush()

    # Prepare command
    cmd = [
        sys.executable,
        "scripts/cli.py",
        "build",
        "--tenant-id",
        "test",
        "--no-container",
        "--test-keypress-file",
        str(key_file),
    ]
    # Start subprocess with stdin PIPE
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=".",
    )
    # Wait for process to exit
    try:
        stdout, stderr = proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise AssertionError("CLI did not exit on 'x' keypress") from None

    # Assert actual DEBUG log messages do not appear in INFO mode
    # (The word "DEBUG" in UI text like "Press 'd' for DEBUG" is fine)
    assert "DEBUG:" not in stdout and "DEBUG " not in stdout
    # Assert process exited
    if proc.returncode != 0:
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
    assert proc.returncode == 0
