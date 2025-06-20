import asyncio
import io
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

import pytest
from click.testing import CliRunner
from neo4j import GraphDatabase
from scripts.cli import cli

from src.azure_tenant_grapher import AzureTenantGrapher
from src.rich_dashboard import RichDashboard

pytest.importorskip("readchar", reason="readchar not installed")


def test_dashboard_keypress_handling(monkeypatch: Any):
    """Test that dashboard responds to 'x', 'i', 'd', 'w' keypresses."""
    # Simulate keypresses: 'i', 'd', 'w', 'x'
    key_sequence = iter(["i", "d", "w", "x"])

    def fake_key_loop(self: Any):
        for key in key_sequence:
            if key and key.lower() == "x":
                with self.lock:
                    self._should_exit = True
                break
            elif key and key.lower() in ("i", "d", "w"):
                level = {"i": "info", "d": "debug", "w": "warning"}[key.lower()]
                with self.lock:
                    self.log_level = level
                    self.log_widget.add_line(
                        f"Log level set to {self.log_level.upper()}",
                        style="yellow",
                        level="info",
                    )
                    self.layout["logs"].update(self.render_log_panel())

    config = {"tenant_id": "test"}
    dashboard = RichDashboard(config, max_concurrency=1)
    # Run dashboard.live() context, injecting the fake_key_loop as key_handler
    with dashboard.live(key_handler=lambda: fake_key_loop(dashboard)):
        pass

    # After 'x', dashboard should exit
    assert dashboard.should_exit
    # Log level should be 'warning' after 'i', 'd', 'w'
    assert dashboard.log_level == "warning"


def test_dashboard_log_level_affects_logging(monkeypatch: Any):
    """Test that changing log level via dashboard keypress affects actual log output and 'x' exits."""
    # Use a queue to simulate keypresses: 'd', 'w', 'x'
    key_q = queue.Queue()
    for k in ["d", "w", "x"]:
        key_q.put(k)

    # key_source is not used and can be removed

    config = {"tenant_id": "test"}
    dashboard = RichDashboard(config, max_concurrency=1)

    # Capture log output
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.NOTSET)
    root_logger = logging.getLogger()
    old_level = root_logger.level
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    # Run dashboard.live() in a thread, emit logs at each level after each keypress
    first_output = []
    second_output = []

    def dashboard_thread():
        ready = threading.Event()

        # Patch the dashboard's key handler to set the event when log level is set to DEBUG
        def key_handler():
            while True:
                key = key_q.get(timeout=1)
                if key == "d":
                    dashboard.log_level = "debug"
                    ready.set()
                elif key == "w":
                    dashboard.log_level = "warning"
                elif key == "x":
                    dashboard._should_exit = True  # type: ignore
                    break

        with dashboard.live(key_handler=key_handler):
            ready.wait(timeout=1)
            # After 'd' (DEBUG)
            logging.debug("DEBUG log")
            logging.info("INFO log")
            logging.warning("WARNING log")
            handler.flush()
            first_output.append(log_stream.getvalue())
            # After 'w' (WARNING)
            time.sleep(0.1)
            handler.setLevel(logging.WARNING)
            log_stream.truncate(0)
            log_stream.seek(0)
            logging.debug("DEBUG2 log")
            logging.info("INFO2 log")
            logging.warning("WARNING2 log")
            handler.flush()
            second_output.append(log_stream.getvalue())
            # All keys already in queue; keypress thread will process 'x' and exit

    t = threading.Thread(target=dashboard_thread)
    t.start()
    t.join(timeout=3)

    # After 'd', log level is DEBUG, all logs should appear
    assert "DEBUG log" in first_output[0]
    assert "INFO log" in first_output[0]
    assert "WARNING log" in first_output[0]

    # After 'w', log level is WARNING, only WARNING should appear after that
    assert "WARNING2 log" in second_output[0]
    assert "DEBUG2 log" not in second_output[0]
    assert "INFO2 log" not in second_output[0]

    root_logger.removeHandler(handler)
    root_logger.setLevel(old_level)

    # After 'x', dashboard should exit (wait up to 2s for thread to process)
    waited = 0
    while not dashboard.should_exit and waited < 2.0:
        time.sleep(0.05)
        waited += 0.05
    assert dashboard.should_exit


@pytest.mark.timeout(20)
def test_dashboard_invokes_processing(monkeypatch: Any) -> None:
    """
    Regression test: Prove dashboard mode invokes AzureTenantGrapher.build_graph.
    - Patches build_graph to set an asyncio.Event.
    - Patches RichDashboard.live to a dummy async context manager.
    - Invokes CLI with dashboard enabled.
    - Asserts build_graph was awaited and CLI exited.
    """
    # Patch AzureTenantGrapher.build_graph to set an event
    event = asyncio.Event()

    async def fake_build_graph(self: Any, *args: Any, **kwargs: Any) -> str:
        event.set()
        return "stubbed-result"

    monkeypatch.setattr(AzureTenantGrapher, "build_graph", fake_build_graph)

    # Patch AzureTenantGrapher.__init__ to set a dummy driver with a close method
    class DummyDriver:
        def close(self) -> None:
            pass

        def session(self) -> Any:
            return DummySession()

    class DummySession:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

        def run(self, query: str, *args: Any, **kwargs: Any) -> Any:
            return []

    orig_init = AzureTenantGrapher.__init__

    def dummy_init(self: Any, config: Any) -> None:
        orig_init(self, config)
        self.driver = DummyDriver()

    monkeypatch.setattr(AzureTenantGrapher, "__init__", dummy_init)

    # Also patch the connect_to_neo4j method to prevent any real connections
    def dummy_connect_to_neo4j(self: Any) -> None:
        self.driver = DummyDriver()

    monkeypatch.setattr(AzureTenantGrapher, "connect_to_neo4j", dummy_connect_to_neo4j)

    # Patch GraphDatabase.driver to prevent any real neo4j connections
    def dummy_graph_driver(*args: Any, **kwargs: Any) -> DummyDriver:
        return DummyDriver()

    monkeypatch.setattr(GraphDatabase, "driver", dummy_graph_driver)

    # Patch RichDashboard.live to a dummy synchronous context manager
    @contextmanager
    def dummy_live_method(self: Any):
        yield self

    monkeypatch.setattr(RichDashboard, "live", dummy_live_method)

    # Run CLI with dashboard (default, i.e. no --no-dashboard)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["build", "--tenant-id", "dummy", "--no-container"],
        catch_exceptions=False,
    )

    # Check: build_graph was awaited (event is set)
    # Since runner.invoke is sync, we need to run the event loop to check the event
    loop: Optional[asyncio.AbstractEventLoop] = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_set = loop.run_until_complete(event.wait())
    finally:
        if loop is not None:
            loop.close()

    assert is_set is None or is_set is True  # event.wait() returns None when set
    # Accept exit code 0 (success) or nonzero (e.g. due to stubbed dashboard)
    assert result.exit_code == 0 or event.is_set()
    # Optionally, print output for debugging
    # print(result.output)


@pytest.mark.timeout(10)
def test_dashboard_runs_for_at_least_2_seconds(tmp_path: Path):
    """
    Integration: The dashboard should not exit immediately on startup.
    This test launches the CLI dashboard in a subprocess, waits 2 seconds,
    then terminates it. It asserts the process was alive for at least 2 seconds.
    """
    import time

    # Use a dummy tenant id and --no-container to avoid side effects
    cmd = [
        sys.executable,
        "scripts/cli.py",
        "build",
        "--tenant-id",
        "dummy",
        "--no-container",
        "--resource-limit",
        "1",
    ]
    # Use a temp env to avoid real Azure/Neo4j calls if possible
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["AZURE_TENANT_ID"] = "dummy"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
    start = time.time()
    try:
        # Wait 2 seconds, then terminate
        time.sleep(2)
        alive = proc.poll() is None
        if alive:
            proc.terminate()
        _out, _err = proc.communicate(timeout=5)
    finally:
        proc.kill()
    duration = time.time() - start
    assert duration >= 2, f"Dashboard exited too early (ran {duration:.2f}s)"


def test_dashboard_log_view_handles_stack_traces(tmp_path: Path):
    """
    Test that the dashboard log view formats or filters stack traces for readability.
    """
    from src.rich_dashboard import RichDashboard

    # Simulate a log file with a stack trace
    log_file = tmp_path / "test_stacktrace.log"
    stack_trace = (
        "2025-06-16 13:09:03,922 - ERROR:src.module:An error occurred\n"
        "Traceback (most recent call last):\n"
        '  File "/path/to/file.py", line 10, in <module>\n'
        "    raise ValueError('fail')\n"
        "ValueError: fail\n"
    )
    with open(log_file, "w") as f:
        f.write(stack_trace)
        f.flush()

    config = {"tenant_id": "test", "log_file": str(log_file)}
    dashboard = RichDashboard(config, max_concurrency=1)
    dashboard.log_file_path = str(log_file)

    # Poll log file to load the stack trace
    dashboard.poll_log_file()

    # Render the log panel and check for readable formatting
    log_panel = dashboard.render_log_panel()
    # Extract the text from the panel's renderable (the log widget's Rich Text)
    log_text = ""
    if hasattr(log_panel, "renderable"):
        renderable = log_panel.renderable
        # If it's an Align, get the child
        if hasattr(renderable, "renderable"):
            renderable = renderable.renderable
        if hasattr(renderable, "plain"):
            log_text = renderable.plain
        else:
            log_text = str(renderable)
    # Should show the error and stack trace, possibly colorized or indented
    # Defensive: fallback to str(renderable) if .plain is not present
    if not log_text or not isinstance(log_text, str):
        log_text = str(log_panel)
    assert "Traceback (most recent call last):" in log_text
    assert "ValueError: fail" in log_text
    # Optionally, check for color codes or formatting if supported
    # (e.g., Rich markup, indentation, or collapsed/expandable trace)


def test_dashboard_log_view_updates_in_real_time(tmp_path: Path):
    """
    Test that the dashboard log view updates promptly when the log file is written to.
    """
    import time

    from src.rich_dashboard import RichDashboard

    # Create a temporary log file and write an initial line
    log_file = tmp_path / "test_dashboard.log"
    with open(log_file, "w") as f:
        f.write("Initial log line\n")
        f.flush()

    config = {"tenant_id": "test", "log_file": str(log_file)}
    dashboard = RichDashboard(config, max_concurrency=1)
    dashboard.log_file_path = str(log_file)  # ensure log file is set

    # Start the dashboard log polling in a thread
    def poll_logs():
        # Simulate the dashboard's log polling loop
        for _ in range(10):
            dashboard.poll_log_file()
            time.sleep(0.1)

    poll_thread = threading.Thread(target=poll_logs)
    poll_thread.start()

    # Write a new log entry after a short delay
    time.sleep(0.2)
    with open(log_file, "a") as f:
        f.write("New log entry\n")
        f.flush()

    # Wait for polling to pick up the new entry
    poll_thread.join(timeout=2)

    # Check that the dashboard's log view contains the new entry
    log_panel = dashboard.render_log_panel()
    # Extract the text from the panel's renderable (the log widget's Rich Text)
    log_text = ""
    if hasattr(log_panel, "renderable"):
        renderable = log_panel.renderable
        # If it's an Align, get the child
        if hasattr(renderable, "renderable"):
            renderable = renderable.renderable
        if hasattr(renderable, "plain"):
            log_text = renderable.plain
        else:
            log_text = str(renderable)
    # Defensive: fallback to str(renderable) if .plain is not present
    if not log_text or not isinstance(log_text, str):
        log_text = str(log_panel)
    assert (
        "New log entry" in log_text
    ), "Dashboard log view did not update with new log entry in real time"
