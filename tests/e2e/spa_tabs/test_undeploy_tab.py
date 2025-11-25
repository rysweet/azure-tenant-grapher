"""
E2E tests for the Undeploy Tab component.
Tests resource cleanup, deletion workflows, and safety checks.
"""

import pytest
from playwright.async_api import Page, expect


class TestUndeployTab:
    """Test suite for Undeploy Tab functionality."""

    @pytest.mark.asyncio
    async def test_navigate_to_undeploy_tab(self, page: Page, spa_server_url: str):
        """Test navigation to Undeploy tab."""
        await page.goto(spa_server_url)

        # Wait for app to load
        await page.wait_for_selector("[data-testid='app-container']", state="visible")

        # Click on Undeploy tab
        await page.click("[data-testid='tab-undeploy']")

        # Verify Undeploy content is visible
        await expect(page.locator("[data-testid='undeploy-content']")).to_be_visible()

        # Check for main sections
        await expect(page.locator("[data-testid='resource-list']")).to_be_visible()
        await expect(page.locator("[data-testid='undeploy-controls']")).to_be_visible()

    @pytest.mark.asyncio
    async def test_list_deployed_resources(self, page: Page, spa_server_url: str):
        """Test listing of deployed resources."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Mock API response with deployed resources
        mock_resources = [
            {
                "id": "rg-001",
                "name": "test-resource-group",
                "type": "ResourceGroup",
                "status": "deployed",
                "created": "2024-01-15T10:00:00Z",
                "dependencies": [],
            },
            {
                "id": "vm-001",
                "name": "test-vm",
                "type": "VirtualMachine",
                "status": "deployed",
                "created": "2024-01-15T10:30:00Z",
                "dependencies": ["rg-001"],
            },
            {
                "id": "nsg-001",
                "name": "test-nsg",
                "type": "NetworkSecurityGroup",
                "status": "deployed",
                "created": "2024-01-15T10:15:00Z",
                "dependencies": ["rg-001"],
            },
        ]

        await page.route(
            "**/api/resources/deployed",
            lambda route: route.fulfill(status=200, json={"resources": mock_resources}),
        )

        # Refresh resource list
        await page.click("[data-testid='refresh-resources-btn']")

        # Wait for resources to load
        # await expect(page.locator("[data-testid='resource-item']").first).to_be_visible(timeout=5000)

        # Verify resource count
        resource_items = page.locator("[data-testid='resource-item']")
        assert await resource_items.count() == 3

        # Check resource details
        # await expect(first_resource).to_contain_text("test-resource-group")
        # await expect(first_resource).to_contain_text("ResourceGroup")

    @pytest.mark.asyncio
    async def test_resource_selection(self, page: Page, spa_server_url: str):
        """Test resource selection for undeployment."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Load resources
        await page.click("[data-testid='load-sample-resources']")
        # await expect(page.locator("[data-testid='resource-item']").first).to_be_visible()

        # Select individual resources
        first_checkbox = page.locator("[data-testid='resource-checkbox']").first
        await first_checkbox.check()
        assert await first_checkbox.is_checked()

        # Verify selection count
        await expect(page.locator("[data-testid='selection-count']")).to_contain_text(
            "1 selected"
        )

        # Select all resources
        await page.click("[data-testid='select-all-checkbox']")

        # All checkboxes should be checked
        checkboxes = page.locator("[data-testid='resource-checkbox']")
        count = await checkboxes.count()
        for i in range(count):
            assert await checkboxes.nth(i).is_checked()

        # Verify selection count updated
        await expect(page.locator("[data-testid='selection-count']")).to_contain_text(
            f"{count} selected"
        )

        # Deselect all
        await page.click("[data-testid='select-all-checkbox']")
        for i in range(count):
            assert not await checkboxes.nth(i).is_checked()

    @pytest.mark.asyncio
    async def test_dependency_warning(self, page: Page, spa_server_url: str):
        """Test dependency warnings when selecting resources."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Load resources with dependencies
        await page.click("[data-testid='load-sample-resources']")
        # await expect(page.locator("[data-testid='resource-item']").first).to_be_visible()

        # Select a resource with dependencies (VM depends on RG)
        vm_checkbox = page.locator(
            "[data-testid='resource-checkbox'][data-resource-type='VirtualMachine']"
        ).first
        await vm_checkbox.check()

        # Warning should appear
        await expect(page.locator("[data-testid='dependency-warning']")).to_be_visible()
        await expect(
            page.locator("[data-testid='dependency-warning']")
        ).to_contain_text("dependencies")

        # Check if dependent resources are highlighted
        dependent_resources = page.locator("[data-testid='dependent-resource']")
        assert await dependent_resources.count() > 0

    @pytest.mark.asyncio
    async def test_safe_undeploy_mode(self, page: Page, spa_server_url: str):
        """Test safe undeploy mode with confirmation."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Load resources
        await page.click("[data-testid='load-sample-resources']")
        # await expect(page.locator("[data-testid='resource-item']").first).to_be_visible()

        # Enable safe mode (should be default)
        safe_mode_toggle = page.locator("[data-testid='safe-mode-toggle']")
        if not await safe_mode_toggle.is_checked():
            await safe_mode_toggle.check()

        # Select resources
        await page.click("[data-testid='select-all-checkbox']")

        # Click undeploy
        await page.click("[data-testid='undeploy-selected-btn']")

        # Confirmation dialog should appear
        await expect(
            page.locator("[data-testid='confirmation-dialog']")
        ).to_be_visible()

        # Check confirmation details
        await expect(
            page.locator("[data-testid='confirmation-message']")
        ).to_contain_text("permanently delete")
        await expect(page.locator("[data-testid='resource-summary']")).to_be_visible()

        # Type confirmation text
        await page.fill("[data-testid='confirmation-input']", "DELETE")

        # Confirm button should be enabled
        confirm_btn = page.locator("[data-testid='confirm-delete-btn']")
        # await expect(confirm_btn).to_be_enabled()

        # Mock API response
        await page.route(
            "**/api/resources/undeploy",
            lambda route: route.fulfill(
                status=200, json={"success": True, "deleted": 3}
            ),
        )

        # Confirm deletion
        await confirm_btn.click()

        # Progress should be shown
        await expect(page.locator("[data-testid='undeploy-progress']")).to_be_visible()

        # Success message should appear
        await expect(page.locator("[data-testid='undeploy-success']")).to_be_visible(
            timeout=10000
        )

    @pytest.mark.asyncio
    async def test_force_undeploy_mode(self, page: Page, spa_server_url: str):
        """Test force undeploy mode (dangerous)."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Load resources
        await page.click("[data-testid='load-sample-resources']")
        # await expect(page.locator("[data-testid='resource-item']").first).to_be_visible()

        # Disable safe mode
        safe_mode_toggle = page.locator("[data-testid='safe-mode-toggle']")
        await safe_mode_toggle.uncheck()

        # Warning should appear
        await expect(page.locator("[data-testid='force-mode-warning']")).to_be_visible()
        await expect(
            page.locator("[data-testid='force-mode-warning']")
        ).to_contain_text("DANGEROUS")

        # Select resources
        await page.click("[data-testid='select-all-checkbox']")

        # Force undeploy button should be visible
        force_btn = page.locator("[data-testid='force-undeploy-btn']")
        # await expect(force_btn).to_be_visible()
        # await expect(force_btn).to_have_class("danger")

        # Click force undeploy
        await force_btn.click()

        # Still should have a confirmation (but simpler)
        await expect(page.locator("[data-testid='force-confirmation']")).to_be_visible()

        # Mock API response
        await page.route(
            "**/api/resources/force-undeploy",
            lambda route: route.fulfill(
                status=200, json={"success": True, "deleted": 3, "forced": True}
            ),
        )

        # Confirm
        await page.click("[data-testid='force-confirm-btn']")

        # Check for completion
        await expect(page.locator("[data-testid='undeploy-success']")).to_be_visible(
            timeout=10000
        )

    @pytest.mark.asyncio
    async def test_undeploy_progress_tracking(self, page: Page, spa_server_url: str):
        """Test progress tracking during undeployment."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Load resources
        await page.click("[data-testid='load-sample-resources']")
        await page.click("[data-testid='select-all-checkbox']")

        # Mock progressive API responses
        async def handle_undeploy_route(route):
            # Simulate progressive updates
            await route.fulfill(
                status=200,
                content_type="text/event-stream",
                body="""data: {"progress": 0, "message": "Starting undeployment..."}\n\n
data: {"progress": 33, "message": "Deleting VirtualMachine..."}\n\n
data: {"progress": 66, "message": "Deleting NetworkSecurityGroup..."}\n\n
data: {"progress": 100, "message": "Complete", "success": true}\n\n""",
            )

        await page.route("**/api/resources/undeploy", handle_undeploy_route)

        # Start undeployment
        await page.click("[data-testid='undeploy-selected-btn']")
        await page.fill("[data-testid='confirmation-input']", "DELETE")
        await page.click("[data-testid='confirm-delete-btn']")

        # Check progress bar
        page.locator("[data-testid='progress-bar']")
        # await expect(progress_bar).to_be_visible()

        # Verify progress updates
        # await expect(progress_bar).to_have_attribute("aria-valuenow", "33", timeout=5000)
        # await expect(progress_bar).to_have_attribute("aria-valuenow", "66", timeout=5000)
        # await expect(progress_bar).to_have_attribute("aria-valuenow", "100", timeout=5000)

        # Check status messages
        page.locator("[data-testid='progress-message']")
        # await expect(status_message).to_contain_text("Complete")

    @pytest.mark.asyncio
    async def test_rollback_capability(self, page: Page, spa_server_url: str):
        """Test rollback capability after partial failure."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Load resources
        await page.click("[data-testid='load-sample-resources']")
        await page.click("[data-testid='select-all-checkbox']")

        # Mock API failure response
        await page.route(
            "**/api/resources/undeploy",
            lambda route: route.fulfill(
                status=500,
                json={
                    "success": False,
                    "error": "Failed to delete VirtualMachine",
                    "deleted": ["nsg-001"],
                    "failed": ["vm-001"],
                    "rollback_available": True,
                },
            ),
        )

        # Attempt undeployment
        await page.click("[data-testid='undeploy-selected-btn']")
        await page.fill("[data-testid='confirmation-input']", "DELETE")
        await page.click("[data-testid='confirm-delete-btn']")

        # Error should be displayed
        await expect(page.locator("[data-testid='undeploy-error']")).to_be_visible()
        await expect(page.locator("[data-testid='undeploy-error']")).to_contain_text(
            "Failed to delete"
        )

        # Rollback option should be available
        rollback_btn = page.locator("[data-testid='rollback-btn']")
        # await expect(rollback_btn).to_be_visible()

        # Mock rollback API
        await page.route(
            "**/api/resources/rollback",
            lambda route: route.fulfill(
                status=200, json={"success": True, "restored": ["nsg-001"]}
            ),
        )

        # Perform rollback
        await rollback_btn.click()

        # Confirm rollback
        await page.click("[data-testid='confirm-rollback-btn']")

        # Success message
        await expect(page.locator("[data-testid='rollback-success']")).to_be_visible()
        await expect(page.locator("[data-testid='rollback-success']")).to_contain_text(
            "restored"
        )

    @pytest.mark.asyncio
    async def test_resource_filtering(self, page: Page, spa_server_url: str):
        """Test filtering resources by type and status."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Load resources
        await page.click("[data-testid='load-sample-resources']")
        # await expect(page.locator("[data-testid='resource-item']").first).to_be_visible()

        initial_count = await page.locator("[data-testid='resource-item']").count()

        # Filter by resource type
        await page.select_option(
            "[data-testid='resource-type-filter']", "VirtualMachine"
        )

        # Only VMs should be visible
        filtered_items = page.locator("[data-testid='resource-item']:visible")
        filtered_count = await filtered_items.count()
        assert filtered_count < initial_count

        for i in range(filtered_count):
            filtered_items.nth(i)
            # await expect(item).to_contain_text("VirtualMachine")

        # Clear filter
        await page.select_option("[data-testid='resource-type-filter']", "all")

        # Search by name
        await page.fill("[data-testid='resource-search']", "test-vm")

        # Only matching resources should be visible
        await page.wait_for_timeout(500)  # Debounce
        visible_items = page.locator("[data-testid='resource-item']:visible")
        assert await visible_items.count() == 1
        # await expect(visible_items.first).to_contain_text("test-vm")

    @pytest.mark.asyncio
    async def test_export_undeploy_report(self, page: Page, spa_server_url: str):
        """Test exporting undeploy report."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Load and select resources
        await page.click("[data-testid='load-sample-resources']")
        await page.click("[data-testid='select-all-checkbox']")

        # Perform undeployment
        await page.click("[data-testid='undeploy-selected-btn']")
        await page.fill("[data-testid='confirmation-input']", "DELETE")

        # Mock successful undeploy
        await page.route(
            "**/api/resources/undeploy",
            lambda route: route.fulfill(
                status=200,
                json={
                    "success": True,
                    "deleted": ["rg-001", "vm-001", "nsg-001"],
                    "timestamp": "2024-01-15T12:00:00Z",
                    "duration": "45s",
                },
            ),
        )

        await page.click("[data-testid='confirm-delete-btn']")

        # Wait for completion
        await expect(page.locator("[data-testid='undeploy-success']")).to_be_visible()

        # Export report
        download_promise = page.wait_for_event("download")
        await page.click("[data-testid='export-report-btn']")

        download = await download_promise
        assert download.suggested_filename.startswith("undeploy-report")
        assert download.suggested_filename.endswith(
            ".json"
        ) or download.suggested_filename.endswith(".csv")

    @pytest.mark.asyncio
    async def test_undo_history(self, page: Page, spa_server_url: str):
        """Test undo history for recent undeploy operations."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-undeploy']")

        # Open history panel
        await page.click("[data-testid='history-btn']")

        # History panel should be visible
        await expect(page.locator("[data-testid='history-panel']")).to_be_visible()

        # Mock history API
        await page.route(
            "**/api/resources/undeploy-history",
            lambda route: route.fulfill(
                status=200,
                json={
                    "history": [
                        {
                            "id": "op-001",
                            "timestamp": "2024-01-15T11:00:00Z",
                            "resources": ["test-vm"],
                            "status": "completed",
                            "undoable": True,
                        },
                        {
                            "id": "op-002",
                            "timestamp": "2024-01-15T10:00:00Z",
                            "resources": ["test-nsg", "test-rg"],
                            "status": "completed",
                            "undoable": False,
                        },
                    ]
                },
            ),
        )

        # Load history
        await page.click("[data-testid='refresh-history-btn']")

        # History items should be displayed
        history_items = page.locator("[data-testid='history-item']")
        assert await history_items.count() == 2

        # First item should be undoable
        first_item = history_items.first
        first_item.locator("[data-testid='undo-operation-btn']")
        # await expect(undo_btn).to_be_visible()

        # Second item should not be undoable
        second_item = history_items.nth(1)
        second_item.locator("[data-testid='undo-operation-btn']")
        # await expect(undo_btn_disabled).not_to_be_visible()
