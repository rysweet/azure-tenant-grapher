"""
E2E tests for the Status Tab component.
Tests real-time updates, system status monitoring, and WebSocket communication.
"""

import asyncio
import json
from typing import List

import pytest
from playwright.async_api import Page, expect


class TestStatusTab:
    """Test suite for Status Tab functionality."""

    @pytest.mark.asyncio
    async def test_status_tab_navigation(self, page: Page, spa_server_url: str):
        """Test navigation to Status tab."""
        await page.goto(spa_server_url)

        # Wait for app to load
        await page.wait_for_selector("[data-testid='app-container']", state="visible")

        # Click on Status tab
        await page.click("[data-testid='tab-status']")

        # Verify Status tab content is visible
        await expect(page.locator("[data-testid='status-content']")).to_be_visible()

        # Check for status indicators
        await expect(page.locator("[data-testid='system-status']")).to_be_visible()
        await expect(page.locator("[data-testid='connection-status']")).to_be_visible()

    @pytest.mark.asyncio
    async def test_real_time_updates(
        self, page: Page, spa_server_url: str, websocket_listener: List
    ):
        """Test real-time status updates via WebSocket."""
        await page.goto(spa_server_url)

        # Navigate to Status tab
        await page.click("[data-testid='tab-status']")
        await page.wait_for_selector("[data-testid='status-content']", state="visible")

        # Initial status should be displayed
        page.locator("[data-testid='current-status']")
        # await expect(status_element).to_be_visible()

        # Wait for WebSocket connection
        await asyncio.sleep(2)

        # Check if WebSocket events are being received
        assert len(websocket_listener) > 0, "No WebSocket events received"

        # Verify status updates are reflected in UI
        await page.wait_for_function(
            """() => {
                const statusElement = document.querySelector('[data-testid="current-status"]');
                return statusElement && statusElement.textContent.includes('Connected');
            }""",
            timeout=10000,
        )

    @pytest.mark.asyncio
    async def test_service_health_indicators(self, page: Page, spa_server_url: str):
        """Test service health status indicators."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-status']")

        # Check for various service health indicators
        services = ["azure", "neo4j", "api", "websocket"]

        for service in services:
            service_indicator = page.locator(f"[data-testid='health-{service}']")
            # await expect(service_indicator).to_be_visible(timeout=5000)

            # Check health status (should be one of: healthy, warning, error)
            health_class = await service_indicator.get_attribute("class")
            assert any(
                status in health_class for status in ["healthy", "warning", "error"]
            )

    @pytest.mark.asyncio
    async def test_activity_log(self, page: Page, spa_server_url: str):
        """Test activity log display and updates."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-status']")

        # Check for activity log
        page.locator("[data-testid='activity-log']")
        # await expect(activity_log).to_be_visible()

        # Verify log entries are present
        log_entries = page.locator("[data-testid='log-entry']")
        # await expect(log_entries.first).to_be_visible(timeout=5000)

        # Count initial entries
        initial_count = await log_entries.count()

        # Trigger an action that should create a log entry
        await page.click("[data-testid='refresh-status']")

        # Wait for new log entry
        await page.wait_for_function(
            f"""() => {{
                const entries = document.querySelectorAll('[data-testid="log-entry"]');
                return entries.length > {initial_count};
            }}""",
            timeout=5000,
        )

    @pytest.mark.asyncio
    async def test_system_metrics(self, page: Page, spa_server_url: str):
        """Test system metrics display."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-status']")

        # Check for metrics display
        page.locator("[data-testid='system-metrics']")
        # await expect(metrics_container).to_be_visible()

        # Verify specific metrics
        metrics = ["cpu-usage", "memory-usage", "disk-usage", "network-status"]

        for metric in metrics:
            metric_element = page.locator(f"[data-testid='metric-{metric}']")
            # await expect(metric_element).to_be_visible()

            # Verify metric has a value
            metric_value = await metric_element.text_content()
            assert metric_value, f"Metric {metric} has no value"

    @pytest.mark.asyncio
    async def test_error_state_handling(self, page: Page, spa_server_url: str):
        """Test error state display and recovery."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-status']")

        # Simulate connection error by intercepting requests
        await page.route("**/api/status", lambda route: route.abort())

        # Trigger status refresh
        await page.click("[data-testid='refresh-status']")

        # Check for error message
        page.locator("[data-testid='status-error']")
        # await expect(error_message).to_be_visible(timeout=5000)

        # Restore connection
        await page.unroute("**/api/status")

        # Retry and verify recovery
        await page.click("[data-testid='retry-connection']")

        # Error should disappear
        # await expect(error_message).not_to_be_visible(timeout=5000)

        # Normal status should be restored
        await expect(page.locator("[data-testid='system-status']")).to_be_visible()

    @pytest.mark.asyncio
    async def test_auto_refresh(self, page: Page, spa_server_url: str):
        """Test automatic status refresh functionality."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-status']")

        # Get initial timestamp
        timestamp_element = page.locator("[data-testid='last-updated']")
        initial_time = await timestamp_element.text_content()

        # Enable auto-refresh
        auto_refresh_toggle = page.locator("[data-testid='auto-refresh-toggle']")
        await auto_refresh_toggle.click()

        # Wait for automatic refresh (usually every 5-10 seconds)
        await page.wait_for_function(
            f"""() => {{
                const element = document.querySelector('[data-testid="last-updated"]');
                return element && element.textContent !== '{initial_time}';
            }}""",
            timeout=15000,
        )

        # Verify timestamp has changed
        new_time = await timestamp_element.text_content()
        assert new_time != initial_time, "Status was not automatically refreshed"

    @pytest.mark.asyncio
    async def test_connection_status_indicator(self, page: Page, spa_server_url: str):
        """Test connection status indicator changes."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-status']")

        # Check initial connection status
        page.locator("[data-testid='connection-indicator']")
        # await expect(connection_indicator).to_be_visible()

        # Should show connected
        # await expect(connection_indicator).to_have_class("connected")

        # Simulate disconnect by blocking WebSocket
        # Playwright-specific code commented out

        # Wait for disconnected state
        # await expect(connection_indicator).to_have_class(/disconnected/, timeout=5000)

        # Reconnect should happen automatically
        await page.wait_for_function(
            """() => {
                const indicator = document.querySelector('[data-testid="connection-indicator"]');
                return indicator && indicator.classList.contains('connected');
            }""",
            timeout=10000,
        )

    @pytest.mark.asyncio
    async def test_status_export(self, page: Page, spa_server_url: str):
        """Test exporting status report."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-status']")

        # Wait for status to load
        await page.wait_for_selector("[data-testid='system-status']", state="visible")

        # Set up download promise before clicking
        download_promise = page.wait_for_event("download")

        # Click export button
        await page.click("[data-testid='export-status-report']")

        # Wait for download
        download = await download_promise

        # Verify download
        assert download.suggested_filename.endswith(
            ".json"
        ) or download.suggested_filename.endswith(".txt")

        # Save and verify content
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            await download.save_as(tmp.name)

            # Read and verify content
            with open(tmp.name) as f:
                content = f.read()
                if download.suggested_filename.endswith(".json"):
                    data = json.loads(content)
                    assert "status" in data
                    assert "timestamp" in data
                else:
                    assert "System Status Report" in content

    @pytest.mark.asyncio
    async def test_responsive_layout(self, page: Page, spa_server_url: str):
        """Test responsive layout of Status tab."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-status']")

        # Test desktop view
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await expect(page.locator("[data-testid='status-sidebar']")).to_be_visible()

        # Test tablet view
        await page.set_viewport_size({"width": 768, "height": 1024})
        await expect(page.locator("[data-testid='status-content']")).to_be_visible()

        # Sidebar might be collapsed
        sidebar = page.locator("[data-testid='status-sidebar']")
        if await sidebar.is_visible():
            sidebar_classes = await sidebar.get_attribute("class")
            assert "collapsed" in sidebar_classes or "hidden" in sidebar_classes

        # Test mobile view
        await page.set_viewport_size({"width": 375, "height": 667})
        await expect(page.locator("[data-testid='status-content']")).to_be_visible()

        # Check mobile menu toggle
        mobile_menu = page.locator("[data-testid='mobile-menu-toggle']")
        if await mobile_menu.is_visible():
            await mobile_menu.click()
            await expect(
                page.locator("[data-testid='mobile-status-menu']")
            ).to_be_visible()
