import asyncio
import queue

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_key", ["x", "X"])
async def test_dashboard_exits_on_x(exit_key):
    """Test that pressing 'x' or 'X' exits the dashboard promptly."""

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
        key_q.put(exit_key)

    keypress_task = asyncio.create_task(send_exit_key())

    # Run the dashboard and assert it exits on 'x' or 'X'
    try:
        await dashboard_manager.run_with_queue_keypress(build_task, key_q=key_q)
        raise AssertionError("Dashboard should have exited on keypress")
    except (DashboardExitException, SystemExit):
        pass  # Expected
    finally:
        if not keypress_task.done():
            keypress_task.cancel()
        if not build_task.done():
            build_task.cancel()
