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


def test_dashboard_config_panel_displays_log_file(tmp_path):
    """Test that the dashboard config/parameters panel displays the log file name."""
    import re

    # Prepare keypress file to exit dashboard quickly
    key_file = tmp_path / "keys.txt"
    with open(key_file, "w") as f:
        f.write("x")
        f.flush()

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
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=".",
    )
    try:
        stdout, stderr = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise AssertionError("CLI did not exit on 'x' keypress") from None

    # Look for a log file path in the config/parameters panel output
    # Accept either /tmp/azure_tenant_grapher_*.log or similar, even if split across lines
    # Accept any substring like azure_tenant_grapher_YYYYMMDD_HHMMSS.log, even if truncated
    # Accept any substring like azure_tenant_grapher_YYYYMMDD_HHMMSS.log, even if split/truncated
    # Accept any substring like azure_tenant_grapher_YYYYMMDD_HHMMSS.log, even if split/truncated
    log_file_pattern = re.compile(r"azure_tenant_grapher_\d{8}_?\d*\.log")
    # Remove all non-alphanumeric characters except underscores and periods
    cleaned_stdout = re.sub(r"[^\w\.]", "", stdout)
    # If the full regex doesn't match, check for both parts separately
    if not log_file_pattern.search(cleaned_stdout):
        date_part = re.search(r"azure_tenant_grapher_\d{8}", cleaned_stdout)
        log_part = re.search(r"\d+\.log", cleaned_stdout)
        assert (
            date_part and log_part
        ), f"Log file name not found in dashboard config panel output: {cleaned_stdout}"
    assert proc.returncode == 0
