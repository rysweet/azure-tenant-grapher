import asyncio
import queue
import threading
import time

import pytest


@pytest.mark.asyncio
async def test_dashboard_exits_within_timeout():
    """Test that pressing 'x' exits the process within 5 seconds."""

    from src.cli_dashboard_manager import CLIDashboardManager, DashboardExitException
    from src.rich_dashboard import RichDashboard

    # Minimal config for dashboard
    mock_config = {
        "tenant_id": "test-tenant",
        "neo4j": {"uri": "bolt://localhost:7688", "user": "neo4j"},
        "azure_openai": {"configured": False},
        "processing": {"batch_size": 5, "parallel_processing": True},
        "logging": {"level": "INFO"},
    }

    dashboard = RichDashboard(config=mock_config, max_concurrency=5)
    dashboard_manager = CLIDashboardManager(dashboard)

    # Mock build task that runs for a long time unless cancelled
    async def mock_build_task():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise

    build_task = asyncio.create_task(mock_build_task())

    # Use a queue to simulate keypresses
    key_q = queue.Queue()

    async def send_exit_key():
        await asyncio.sleep(1)
        key_q.put("x")

    keypress_task = asyncio.create_task(send_exit_key())

    # Track if the dashboard manager exits
    exit_raised = False
    start_time = time.time()

    try:
        await dashboard_manager.run_with_queue_keypress(build_task, key_q=key_q)
        raise AssertionError("Dashboard should have exited on keypress")
    except (DashboardExitException, SystemExit):
        exit_raised = True
    finally:
        end_time = time.time()
        elapsed = end_time - start_time

        if not keypress_task.done():
            keypress_task.cancel()
        if not build_task.done():
            build_task.cancel()

    assert exit_raised, "DashboardExitException should have been raised"
    assert elapsed < 5.0, (
        f"Dashboard exit took too long: {elapsed:.2f}s (should be < 5s)"
    )


@pytest.mark.asyncio
async def test_real_process_exit_simulation():
    """Test that simulates the actual CLI exit behavior."""

    from src.cli_dashboard_manager import CLIDashboardManager, DashboardExitException
    from src.rich_dashboard import RichDashboard

    # Track active threads before and after
    initial_threads = threading.active_count()

    mock_config = {
        "tenant_id": "test-tenant",
        "neo4j": {"uri": "bolt://localhost:7688", "user": "neo4j"},
        "azure_openai": {"configured": False},
        "processing": {"batch_size": 5, "parallel_processing": True},
        "logging": {"level": "INFO"},
    }

    dashboard = RichDashboard(config=mock_config, max_concurrency=5)
    dashboard_manager = CLIDashboardManager(dashboard)

    async def mock_build_task():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise

    build_task = asyncio.create_task(mock_build_task())
    key_q = queue.Queue()

    async def send_exit_key():
        await asyncio.sleep(0.5)
        key_q.put("x")

    keypress_task = asyncio.create_task(send_exit_key())

    # This should raise DashboardExitException
    with pytest.raises(DashboardExitException):
        await dashboard_manager.run_with_queue_keypress(build_task, key_q=key_q)

    # Clean up
    if not keypress_task.done():
        keypress_task.cancel()
    if not build_task.done():
        build_task.cancel()

    # Give a moment for threads to clean up
    await asyncio.sleep(0.5)

    # Check that thread count returns close to initial
    final_threads = threading.active_count()
    # Allow some tolerance for test framework threads
    assert final_threads <= initial_threads + 2, (
        f"Thread leak detected: {initial_threads} -> {final_threads}"
    )
