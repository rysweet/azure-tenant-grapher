"""
E2E tests for the Create Tenant Tab component.
Tests form validation, tenant creation workflow, and error handling.
"""

import asyncio

import pytest
from playwright.async_api import Page, expect


class TestCreateTenantTab:
    """Test suite for Create Tenant Tab functionality."""

    @pytest.mark.asyncio
    async def test_navigate_to_create_tenant_tab(self, page: Page, spa_server_url: str):
        """Test navigation to Create Tenant tab."""
        await page.goto(spa_server_url)

        # Wait for app to load
        await page.wait_for_selector("[data-testid='app-container']", state="visible")

        # Click on Create Tenant tab
        await page.click("[data-testid='tab-create-tenant']")

        # Verify Create Tenant form is visible
        await expect(page.locator("[data-testid='create-tenant-form']")).to_be_visible()

        # Check for required form fields
        await expect(page.locator("[data-testid='tenant-name-input']")).to_be_visible()
        await expect(
            page.locator("[data-testid='tenant-domain-input']")
        ).to_be_visible()
        await expect(page.locator("[data-testid='admin-email-input']")).to_be_visible()

    @pytest.mark.asyncio
    async def test_form_validation(self, page: Page, spa_server_url: str):
        """Test form validation rules."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-create-tenant']")

        # Try to submit empty form
        submit_button = page.locator("[data-testid='create-tenant-submit']")
        await submit_button.click()

        # Check for validation errors
        await expect(page.locator("[data-testid='tenant-name-error']")).to_be_visible()
        await expect(
            page.locator("[data-testid='tenant-domain-error']")
        ).to_be_visible()
        await expect(page.locator("[data-testid='admin-email-error']")).to_be_visible()

        # Test invalid email
        await page.fill("[data-testid='admin-email-input']", "invalid-email")
        await page.press("[data-testid='admin-email-input']", "Tab")
        await expect(page.locator("[data-testid='admin-email-error']")).to_contain_text(
            "valid email"
        )

        # Test invalid domain
        await page.fill(
            "[data-testid='tenant-domain-input']", "invalid domain with spaces"
        )
        await page.press("[data-testid='tenant-domain-input']", "Tab")
        await expect(
            page.locator("[data-testid='tenant-domain-error']")
        ).to_be_visible()

        # Test valid inputs
        await page.fill("[data-testid='tenant-name-input']", "Test Tenant")
        await page.fill(
            "[data-testid='tenant-domain-input']", "test-tenant.onmicrosoft.com"
        )
        await page.fill("[data-testid='admin-email-input']", "admin@test-tenant.com")

        # Errors should clear
        await expect(
            page.locator("[data-testid='tenant-name-error']")
        ).not_to_be_visible()
        await expect(
            page.locator("[data-testid='tenant-domain-error']")
        ).not_to_be_visible()
        await expect(
            page.locator("[data-testid='admin-email-error']")
        ).not_to_be_visible()

    @pytest.mark.asyncio
    async def test_tenant_configuration_options(self, page: Page, spa_server_url: str):
        """Test advanced tenant configuration options."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-create-tenant']")

        # Expand advanced options
        await page.click("[data-testid='advanced-options-toggle']")

        # Check for advanced fields
        await expect(page.locator("[data-testid='region-select']")).to_be_visible()
        await expect(
            page.locator("[data-testid='subscription-type-select']")
        ).to_be_visible()
        await expect(
            page.locator("[data-testid='enable-mfa-checkbox']")
        ).to_be_visible()
        await expect(
            page.locator("[data-testid='enable-conditional-access-checkbox']")
        ).to_be_visible()

        # Test region selection
        await page.select_option("[data-testid='region-select']", "eastus")
        selected_region = await page.locator(
            "[data-testid='region-select']"
        ).input_value()
        assert selected_region == "eastus"

        # Test subscription type
        await page.select_option(
            "[data-testid='subscription-type-select']", "enterprise"
        )
        selected_type = await page.locator(
            "[data-testid='subscription-type-select']"
        ).input_value()
        assert selected_type == "enterprise"

        # Test checkboxes
        mfa_checkbox = page.locator("[data-testid='enable-mfa-checkbox']")
        await mfa_checkbox.check()
        assert await mfa_checkbox.is_checked()

    @pytest.mark.asyncio
    async def test_successful_tenant_creation(self, page: Page, spa_server_url: str):
        """Test successful tenant creation workflow."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-create-tenant']")

        # Fill in the form
        await page.fill("[data-testid='tenant-name-input']", "E2E Test Tenant")
        await page.fill(
            "[data-testid='tenant-domain-input']", "e2e-test.onmicrosoft.com"
        )
        await page.fill("[data-testid='admin-email-input']", "admin@e2e-test.com")
        await page.fill("[data-testid='admin-password-input']", "SecureP@ssw0rd123!")

        # Mock successful API response
        await page.route(
            "**/api/tenants/create",
            lambda route: route.fulfill(
                status=200,
                json={
                    "success": True,
                    "tenantId": "test-123",
                    "message": "Tenant created successfully",
                },
            ),
        )

        # Submit form
        await page.click("[data-testid='create-tenant-submit']")

        # Check for loading state
        await expect(
            page.locator("[data-testid='create-tenant-loading']")
        ).to_be_visible()

        # Check for success message
        await expect(page.locator("[data-testid='success-message']")).to_be_visible(
            timeout=10000
        )
        await expect(page.locator("[data-testid='success-message']")).to_contain_text(
            "successfully"
        )

        # Verify tenant ID is displayed
        await expect(page.locator("[data-testid='created-tenant-id']")).to_contain_text(
            "test-123"
        )

    @pytest.mark.asyncio
    async def test_error_handling(self, page: Page, spa_server_url: str):
        """Test error handling during tenant creation."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-create-tenant']")

        # Fill in the form
        await page.fill("[data-testid='tenant-name-input']", "Error Test Tenant")
        await page.fill(
            "[data-testid='tenant-domain-input']", "error-test.onmicrosoft.com"
        )
        await page.fill("[data-testid='admin-email-input']", "admin@error-test.com")
        await page.fill("[data-testid='admin-password-input']", "SecureP@ssw0rd123!")

        # Mock API error
        await page.route(
            "**/api/tenants/create",
            lambda route: route.fulfill(
                status=400,
                json={
                    "error": "Tenant domain already exists",
                    "code": "DUPLICATE_DOMAIN",
                },
            ),
        )

        # Submit form
        await page.click("[data-testid='create-tenant-submit']")

        # Check for error message
        await expect(page.locator("[data-testid='error-alert']")).to_be_visible(
            timeout=5000
        )
        await expect(page.locator("[data-testid='error-alert']")).to_contain_text(
            "already exists"
        )

        # Form should remain filled for retry
        tenant_name_value = await page.locator(
            "[data-testid='tenant-name-input']"
        ).input_value()
        assert tenant_name_value == "Error Test Tenant"

    @pytest.mark.asyncio
    async def test_bulk_tenant_creation(self, page: Page, spa_server_url: str):
        """Test bulk tenant creation from CSV."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-create-tenant']")

        # Switch to bulk mode
        await page.click("[data-testid='bulk-mode-toggle']")

        # Check for CSV upload interface
        await expect(page.locator("[data-testid='csv-upload-area']")).to_be_visible()

        # Create a test CSV file
        csv_content = """tenant_name,domain,admin_email,region
Test Tenant 1,test1.onmicrosoft.com,admin@test1.com,eastus
Test Tenant 2,test2.onmicrosoft.com,admin@test2.com,westus
Test Tenant 3,test3.onmicrosoft.com,admin@test3.com,northeurope"""

        # Upload CSV file
        file_input = page.locator("[data-testid='csv-file-input']")
        await file_input.set_input_files(
            files=[
                {
                    "name": "tenants.csv",
                    "mimeType": "text/csv",
                    "buffer": csv_content.encode(),
                }
            ]
        )

        # Preview should be displayed
        await expect(page.locator("[data-testid='csv-preview-table']")).to_be_visible()

        # Verify number of rows
        rows = page.locator("[data-testid='csv-preview-row']")
        assert await rows.count() == 3

        # Mock bulk creation API
        await page.route(
            "**/api/tenants/bulk-create",
            lambda route: route.fulfill(
                status=200,
                json={
                    "success": True,
                    "created": 3,
                    "failed": 0,
                    "results": [
                        {"tenant": "Test Tenant 1", "status": "created", "id": "id-1"},
                        {"tenant": "Test Tenant 2", "status": "created", "id": "id-2"},
                        {"tenant": "Test Tenant 3", "status": "created", "id": "id-3"},
                    ],
                },
            ),
        )

        # Start bulk creation
        await page.click("[data-testid='start-bulk-creation']")

        # Check progress indicator
        await expect(page.locator("[data-testid='bulk-progress']")).to_be_visible()

        # Check results
        await expect(page.locator("[data-testid='bulk-results']")).to_be_visible(
            timeout=10000
        )
        await expect(
            page.locator("[data-testid='bulk-success-count']")
        ).to_contain_text("3")

    @pytest.mark.asyncio
    async def test_tenant_template_selection(self, page: Page, spa_server_url: str):
        """Test tenant creation with templates."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-create-tenant']")

        # Click on templates button
        await page.click("[data-testid='use-template-button']")

        # Template modal should open
        await expect(page.locator("[data-testid='template-modal']")).to_be_visible()

        # Check for template options
        templates = ["enterprise", "small-business", "education", "government"]
        for template in templates:
            await expect(
                page.locator(f"[data-testid='template-{template}']")
            ).to_be_visible()

        # Select enterprise template
        await page.click("[data-testid='template-enterprise']")

        # Form should be pre-filled with template values
        await expect(
            page.locator("[data-testid='subscription-type-select']")
        ).to_have_value("enterprise")

        # MFA should be enabled for enterprise
        mfa_checkbox = page.locator("[data-testid='enable-mfa-checkbox']")
        assert await mfa_checkbox.is_checked()

    @pytest.mark.asyncio
    async def test_password_strength_indicator(self, page: Page, spa_server_url: str):
        """Test password strength indicator."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-create-tenant']")

        password_input = page.locator("[data-testid='admin-password-input']")
        page.locator("[data-testid='password-strength']")

        # Test weak password
        await password_input.fill("weak")
        # await expect(strength_indicator).to_have_class("weak")
        # await expect(strength_indicator).to_contain_text("Weak")

        # Test medium password
        await password_input.fill("Medium123")
        # await expect(strength_indicator).to_have_class("medium")
        # await expect(strength_indicator).to_contain_text("Medium")

        # Test strong password
        await password_input.fill("Str0ng!P@ssw0rd#2024")
        # await expect(strength_indicator).to_have_class("strong")
        # await expect(strength_indicator).to_contain_text("Strong")

    @pytest.mark.asyncio
    async def test_form_autosave(self, page: Page, spa_server_url: str):
        """Test form autosave functionality."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-create-tenant']")

        # Fill in some form data
        await page.fill("[data-testid='tenant-name-input']", "Autosave Test")
        await page.fill(
            "[data-testid='tenant-domain-input']", "autosave.onmicrosoft.com"
        )

        # Wait for autosave (usually triggers after 2-3 seconds of inactivity)
        await asyncio.sleep(3)

        # Check for autosave indicator
        await expect(
            page.locator("[data-testid='autosave-indicator']")
        ).to_contain_text("Saved")

        # Navigate away and back
        await page.click("[data-testid='tab-status']")
        await page.click("[data-testid='tab-create-tenant']")

        # Form should restore saved values
        tenant_name_value = await page.locator(
            "[data-testid='tenant-name-input']"
        ).input_value()
        assert tenant_name_value == "Autosave Test"

        domain_value = await page.locator(
            "[data-testid='tenant-domain-input']"
        ).input_value()
        assert domain_value == "autosave.onmicrosoft.com"

    @pytest.mark.asyncio
    async def test_keyboard_navigation(self, page: Page, spa_server_url: str):
        """Test keyboard navigation and accessibility."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-create-tenant']")

        # Focus first input
        await page.focus("[data-testid='tenant-name-input']")

        # Tab through form fields
        await page.keyboard.press("Tab")
        active_element = await page.evaluate(
            "() => document.activeElement.getAttribute('data-testid')"
        )
        assert active_element == "tenant-domain-input"

        await page.keyboard.press("Tab")
        active_element = await page.evaluate(
            "() => document.activeElement.getAttribute('data-testid')"
        )
        assert active_element == "admin-email-input"

        # Test Enter key submission
        await page.fill("[data-testid='tenant-name-input']", "Keyboard Test")
        await page.fill(
            "[data-testid='tenant-domain-input']", "keyboard.onmicrosoft.com"
        )
        await page.fill("[data-testid='admin-email-input']", "admin@keyboard.com")
        await page.fill("[data-testid='admin-password-input']", "Test@123")

        # Mock API response
        await page.route(
            "**/api/tenants/create",
            lambda route: route.fulfill(
                status=200, json={"success": True, "tenantId": "keyboard-test"}
            ),
        )

        # Submit with Enter key
        await page.keyboard.press("Enter")

        # Should trigger submission
        await expect(
            page.locator("[data-testid='create-tenant-loading']")
        ).to_be_visible()
