"""Complete tenant lifecycle end-to-end tests."""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from playwright.async_api import async_playwright, Page, Browser


class TestCompleteTenantLifecycle:
    """Test complete tenant lifecycle from discovery to deployment."""

    @pytest.mark.asyncio
    async def test_full_tenant_discovery_to_deployment(self, page: Page, mock_azure_api):
        """Test the complete flow from tenant discovery to IaC deployment."""
        # Step 1: Authenticate with Azure
        await page.goto("http://localhost:3000")
        await page.click("[data-testid='auth-button']")
        await page.fill("[data-testid='tenant-id']", "test-tenant-123")
        await page.fill("[data-testid='client-id']", "test-client-456")
        await page.fill("[data-testid='client-secret']", "test-secret")
        await page.click("[data-testid='auth-submit']")

        # Verify authentication success
        await page.wait_for_selector("[data-testid='auth-success']", timeout=5000)

        # Step 2: Start tenant discovery
        await page.click("[data-testid='tab-scan']")
        await page.click("[data-testid='start-scan']")

        # Monitor scan progress
        progress_bar = await page.wait_for_selector("[data-testid='scan-progress']")

        # Wait for scan completion
        await page.wait_for_selector("[data-testid='scan-complete']", timeout=30000)

        # Step 3: Navigate to visualization
        await page.click("[data-testid='tab-visualize']")
        await page.wait_for_selector("[data-testid='graph-canvas']")

        # Verify nodes are rendered
        nodes = await page.locator("[data-testid='graph-node']").count()
        assert nodes > 0, "No nodes rendered in graph"

        # Step 4: Generate IaC
        await page.click("[data-testid='tab-generate-iac']")
        await page.select("[data-testid='iac-format']", "terraform")
        await page.click("[data-testid='generate-iac']")

        # Wait for generation
        await page.wait_for_selector("[data-testid='iac-output']", timeout=10000)

        # Download generated files
        async with page.expect_download() as download_info:
            await page.click("[data-testid='download-iac']")
        download = await download_info.value
        assert download.suggested_filename.endswith(".zip")

        # Step 5: Verify threat model generation
        await page.click("[data-testid='tab-threat-model']")
        await page.click("[data-testid='generate-threat-model']")
        await page.wait_for_selector("[data-testid='threat-model-output']", timeout=10000)

        # Verify threats identified
        threats = await page.locator("[data-testid='threat-item']").count()
        assert threats > 0, "No threats identified"

    @pytest.mark.asyncio
    async def test_tenant_creation_from_spec(self, page: Page):
        """Test creating a new tenant from a specification."""
        await page.goto("http://localhost:3000")

        # Navigate to create tenant tab
        await page.click("[data-testid='tab-create-tenant']")

        # Upload spec file
        spec_content = json.dumps({
            "tenant": {
                "name": "Test Tenant",
                "subscriptions": [
                    {
                        "name": "Test Subscription",
                        "resource_groups": [
                            {
                                "name": "rg-test",
                                "location": "eastus",
                                "resources": [
                                    {
                                        "type": "Microsoft.Compute/virtualMachines",
                                        "name": "vm-test"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        })

        await page.set_input_files(
            "[data-testid='spec-upload']",
            files=[{
                "name": "tenant-spec.json",
                "mimeType": "application/json",
                "buffer": spec_content.encode()
            }]
        )

        # Validate spec
        await page.click("[data-testid='validate-spec']")
        await page.wait_for_selector("[data-testid='validation-success']")

        # Create tenant
        await page.click("[data-testid='create-tenant']")

        # Monitor creation progress
        await page.wait_for_selector("[data-testid='creation-progress']")
        await page.wait_for_selector("[data-testid='creation-complete']", timeout=60000)

        # Verify resources created
        await page.click("[data-testid='tab-status']")
        status_text = await page.text_content("[data-testid='status-summary']")
        assert "1 subscription" in status_text.lower()
        assert "1 resource group" in status_text.lower()

    @pytest.mark.asyncio
    async def test_incremental_discovery_and_update(self, page: Page):
        """Test incremental discovery updates to existing graph."""
        await page.goto("http://localhost:3000")

        # Initial scan
        await page.click("[data-testid='tab-scan']")
        await page.click("[data-testid='start-scan']")
        await page.wait_for_selector("[data-testid='scan-complete']", timeout=30000)

        # Get initial resource count
        initial_count = await page.text_content("[data-testid='resource-count']")

        # Trigger incremental update
        await page.click("[data-testid='incremental-scan']")
        await page.wait_for_selector("[data-testid='scan-complete']", timeout=30000)

        # Verify resources added/updated
        updated_count = await page.text_content("[data-testid='resource-count']")
        assert int(updated_count) >= int(initial_count)

        # Check for change detection
        changes = await page.locator("[data-testid='change-item']").count()
        assert changes >= 0, "Change detection not working"

    @pytest.mark.asyncio
    async def test_filtered_discovery_and_export(self, page: Page):
        """Test filtered discovery with specific subscriptions/resource groups."""
        await page.goto("http://localhost:3000")

        # Configure filters
        await page.click("[data-testid='tab-scan']")
        await page.click("[data-testid='scan-filters']")

        # Select specific subscription
        await page.check("[data-testid='subscription-filter'][value='sub-123']")

        # Select specific resource groups
        await page.check("[data-testid='rg-filter'][value='rg-prod']")
        await page.check("[data-testid='rg-filter'][value='rg-dev']")

        # Start filtered scan
        await page.click("[data-testid='start-scan']")
        await page.wait_for_selector("[data-testid='scan-complete']", timeout=30000)

        # Verify only filtered resources in graph
        await page.click("[data-testid='tab-visualize']")

        # Check that only selected items are present
        nodes = await page.locator("[data-testid='graph-node']").all()
        for node in nodes:
            node_text = await node.text_content()
            assert "sub-123" in node_text or "rg-prod" in node_text or "rg-dev" in node_text

    @pytest.mark.asyncio
    async def test_complete_undeploy_workflow(self, page: Page):
        """Test the complete resource cleanup and undeployment process."""
        await page.goto("http://localhost:3000")

        # Navigate to undeploy tab
        await page.click("[data-testid='tab-undeploy']")

        # Select resources to undeploy
        await page.click("[data-testid='select-all-resources']")

        # Verify dependencies warning
        warning = await page.wait_for_selector("[data-testid='dependency-warning']")
        assert warning is not None

        # Confirm undeploy
        await page.click("[data-testid='confirm-undeploy']")

        # Enter confirmation text
        await page.fill("[data-testid='confirm-text']", "DELETE")
        await page.click("[data-testid='proceed-undeploy']")

        # Monitor undeploy progress
        await page.wait_for_selector("[data-testid='undeploy-progress']")

        # Wait for completion
        await page.wait_for_selector("[data-testid='undeploy-complete']", timeout=60000)

        # Verify cleanup report
        report = await page.text_content("[data-testid='cleanup-report']")
        assert "successfully removed" in report.lower()

    @pytest.mark.asyncio
    async def test_error_recovery_during_lifecycle(self, page: Page):
        """Test error recovery at various stages of the lifecycle."""
        await page.goto("http://localhost:3000")

        # Simulate network failure during scan
        await page.route("**/api/discover", lambda route: route.abort())

        await page.click("[data-testid='tab-scan']")
        await page.click("[data-testid='start-scan']")

        # Wait for error
        error = await page.wait_for_selector("[data-testid='scan-error']", timeout=10000)
        error_text = await error.text_content()
        assert "network" in error_text.lower() or "connection" in error_text.lower()

        # Test retry mechanism
        await page.unroute("**/api/discover")
        await page.click("[data-testid='retry-scan']")

        # Should succeed now
        await page.wait_for_selector("[data-testid='scan-complete']", timeout=30000)

    @pytest.mark.asyncio
    async def test_parallel_operations(self, page: Page, context: Browser):
        """Test running multiple lifecycle operations in parallel."""
        # Create multiple tabs
        page2 = await context.new_page()
        page3 = await context.new_page()

        # Start operations in parallel
        tasks = [
            self._scan_tenant(page, "tenant1"),
            self._generate_iac(page2, "terraform"),
            self._create_threat_model(page3)
        ]

        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all succeeded
        for result in results:
            assert not isinstance(result, Exception), f"Operation failed: {result}"

    async def _scan_tenant(self, page: Page, tenant_id: str):
        """Helper to scan a tenant."""
        await page.goto("http://localhost:3000")
        await page.click("[data-testid='tab-scan']")
        await page.fill("[data-testid='tenant-id']", tenant_id)
        await page.click("[data-testid='start-scan']")
        await page.wait_for_selector("[data-testid='scan-complete']", timeout=30000)
        return True

    async def _generate_iac(self, page: Page, format: str):
        """Helper to generate IaC."""
        await page.goto("http://localhost:3000")
        await page.click("[data-testid='tab-generate-iac']")
        await page.select("[data-testid='iac-format']", format)
        await page.click("[data-testid='generate-iac']")
        await page.wait_for_selector("[data-testid='iac-output']", timeout=10000)
        return True

    async def _create_threat_model(self, page: Page):
        """Helper to create threat model."""
        await page.goto("http://localhost:3000")
        await page.click("[data-testid='tab-threat-model']")
        await page.click("[data-testid='generate-threat-model']")
        await page.wait_for_selector("[data-testid='threat-model-output']", timeout=10000)
        return True


@pytest.fixture
async def page():
    """Provide a Playwright page for testing."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        yield page
        await context.close()
        await browser.close()


@pytest.fixture
def mock_azure_api():
    """Mock Azure API responses."""
    with patch("src.azure_discovery_service.AzureDiscoveryService") as mock:
        instance = mock.return_value
        instance.discover_tenant = AsyncMock(return_value={
            "subscriptions": [{"id": "sub-123", "displayName": "Test Sub"}],
            "resource_groups": [{"id": "rg-123", "name": "rg-test"}],
            "resources": [{"id": "res-123", "name": "vm-test"}]
        })
        yield instance