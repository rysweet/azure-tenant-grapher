import asyncio

from src.rich_dashboard import RichDashboard


async def main():
    # Dummy config for testing
    config = {"tenant_id": "test-tenant", "log_file": "test.log"}
    dashboard = RichDashboard(config, max_concurrency=3)

    # Simulate log output and progress
    dashboard.log_info("Test INFO log")
    dashboard.add_error("Test ERROR log")
    dashboard.update_progress(
        processed=1,
        total=10,
        successful=1,
        failed=0,
        skipped=0,
        llm_generated=1,
        llm_skipped=0,
        llm_in_flight=0,
    )

    print(
        "Dashboard test started. Try pressing 'x', 'i', 'd', or 'w' while the dashboard is running."
    )
    with dashboard.live():
        # Simulate ongoing updates
        for i in range(2, 6):
            await asyncio.sleep(1)
            dashboard.log_info(f"Processing item {i}")
            dashboard.update_progress(
                processed=i,
                total=10,
                successful=i,
                failed=0,
                skipped=0,
                llm_generated=i,
                llm_skipped=0,
                llm_in_flight=0,
            )
        # Wait for user to exit with 'x'
        while not dashboard.should_exit:
            await asyncio.sleep(0.2)


if __name__ == "__main__":
    asyncio.run(main())
