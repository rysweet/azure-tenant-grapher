#!/usr/bin/env python3
"""
Test script to verify that the 'x' keypress properly exits the dashboard with real keyboard input.

This script runs the actual dashboard and simulates a real 'x' keypress.
"""

import asyncio
import queue
import sys
import time
from pathlib import Path

# Add the src directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_real_dashboard_exit():
    """Test that 'x' keypress exits the dashboard properly with real keyboard simulation."""

    # Import required modules
    from src.cli_dashboard_manager import CLIDashboardManager, DashboardExitException
    from src.rich_dashboard import DashboardExit, RichDashboard

    print("🧪 Testing REAL dashboard exit functionality...")

    # Create a mock config
    mock_config = {
        "tenant_id": "test-tenant",
        "neo4j": {"uri": "bolt://localhost:7688", "user": "neo4j"},
        "azure_openai": {"configured": False},
        "processing": {"batch_size": 5, "parallel_processing": True},
        "logging": {"level": "INFO"},
    }

    # Create dashboard
    dashboard = RichDashboard(config=mock_config, max_concurrency=5)

    # Create dashboard manager
    dashboard_manager = CLIDashboardManager(dashboard)

    # Create a mock build task that runs for a long time
    async def mock_build_task():
        """Mock build task that would run for 60 seconds if not cancelled."""
        try:
            print("📄 Mock build task started...")
            await asyncio.sleep(60)  # Should be cancelled before this completes
            return "mock build completed"
        except asyncio.CancelledError:
            print("📄 Mock build task was cancelled (this is expected)")
            raise

    # Create the build task
    build_task = asyncio.create_task(mock_build_task())

    # Use queue-based keypress to simulate real keypress
    print("🚀 Starting dashboard with queue-based keypress test...")
    start_time = time.time()

    # Create a queue and add an 'x' after a delay
    key_q = queue.Queue()

    async def send_x_keypress():
        await asyncio.sleep(2)  # Wait 2 seconds
        print("📝 Sending 'x' keypress...")
        key_q.put("x")
        print("📝 'x' keypress sent to queue!")

    # Start the keypress sender
    keypress_task = asyncio.create_task(send_x_keypress())

    try:
        # Run the dashboard with the correct queue parameter
        await dashboard_manager.run_with_queue_keypress(build_task, key_q)
        print("❌ ERROR: Dashboard should have raised DashboardExitException!")
        return False

    except DashboardExitException as e:
        elapsed = time.time() - start_time
        print(f"✅ SUCCESS: Dashboard exited properly with DashboardExitException: {e}")
        print(f"⏱️  Exit took {elapsed:.2f} seconds")

        # Verify the build task was cancelled
        if build_task.cancelled():
            print("✅ SUCCESS: Build task was properly cancelled")
        else:
            print("❌ ERROR: Build task should have been cancelled")
            return False

        return True

    except DashboardExit as e:
        elapsed = time.time() - start_time
        print(f"✅ SUCCESS: Dashboard exited properly with DashboardExit: {e}")
        print(f"⏱️  Exit took {elapsed:.2f} seconds")

        # Verify the build task was cancelled
        if build_task.cancelled():
            print("✅ SUCCESS: Build task was properly cancelled")
        else:
            print("❌ ERROR: Build task should have been cancelled")
            return False

        return True

    except Exception as e:
        print(f"❌ ERROR: Unexpected exception: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Clean up tasks
        if not keypress_task.done():
            keypress_task.cancel()
        if not build_task.done():
            build_task.cancel()


async def main():
    """Main test function."""
    print("=" * 60)
    print("🧪 REAL DASHBOARD EXIT TEST")
    print("=" * 60)

    try:
        success = await test_real_dashboard_exit()

        print("\n" + "=" * 60)
        if success:
            print("🎉 ALL TESTS PASSED! Dashboard exit functionality works correctly.")
            print("✅ The 'x' keypress properly exits the dashboard.")
        else:
            print("❌ TEST FAILED! Dashboard exit functionality is broken.")
            sys.exit(1)
        print("=" * 60)

    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
