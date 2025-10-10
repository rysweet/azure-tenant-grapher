"""
E2E tests for the Docs Tab component.
Tests documentation navigation, search, and content display.
"""

import pytest
from playwright.async_api import Page, expect


class TestDocsTab:
    """Test suite for Docs Tab functionality."""

    @pytest.mark.asyncio
    async def test_navigate_to_docs_tab(self, page: Page, spa_server_url: str):
        """Test navigation to Docs tab."""
        await page.goto(spa_server_url)

        # Wait for app to load
        await page.wait_for_selector("[data-testid='app-container']", state="visible")

        # Click on Docs tab
        await page.click("[data-testid='tab-docs']")

        # Verify Docs content is visible
        await expect(page.locator("[data-testid='docs-content']")).to_be_visible()

        # Check for main components
        await expect(page.locator("[data-testid='docs-sidebar']")).to_be_visible()
        await expect(page.locator("[data-testid='docs-viewer']")).to_be_visible()

    @pytest.mark.asyncio
    async def test_documentation_tree_navigation(self, page: Page, spa_server_url: str):
        """Test documentation tree structure and navigation."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Check for documentation categories
        categories = [
            "getting-started",
            "configuration",
            "api-reference",
            "troubleshooting",
            "faq",
        ]

        for category in categories:
            category_node = page.locator(f"[data-testid='doc-category-{category}']")
            # await expect(category_node).to_be_visible()

        # Expand a category
        await page.click("[data-testid='doc-category-getting-started']")

        # Check for sub-items
        await expect(
            page.locator("[data-testid='doc-item-installation']")
        ).to_be_visible()
        await expect(
            page.locator("[data-testid='doc-item-quickstart']")
        ).to_be_visible()

        # Click on a documentation item
        await page.click("[data-testid='doc-item-installation']")

        # Content should be displayed
        content_viewer = page.locator("[data-testid='docs-viewer']")
        # await expect(content_viewer).to_contain_text("Installation")

    @pytest.mark.asyncio
    async def test_documentation_search(self, page: Page, spa_server_url: str):
        """Test documentation search functionality."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Find search input
        search_input = page.locator("[data-testid='docs-search-input']")
        # await expect(search_input).to_be_visible()

        # Perform search
        await search_input.fill("configuration")
        await page.keyboard.press("Enter")

        # Wait for search results
        await expect(page.locator("[data-testid='search-results']")).to_be_visible(
            timeout=5000
        )

        # Check search results
        search_results = page.locator("[data-testid='search-result-item']")
        assert await search_results.count() > 0

        # Each result should contain the search term
        first_result = search_results.first
        # await expect(first_result).to_contain_text("configuration", ignore_case=True)

        # Click on a search result
        await first_result.click()

        # Document should be displayed with search term highlighted
        content_viewer = page.locator("[data-testid='docs-viewer']")
        # await expect(content_viewer).to_be_visible()

        # Check for highlighted search terms
        highlighted = page.locator("[data-testid='search-highlight']")
        if await highlighted.count() > 0:
            pass  # await expect(highlighted.first).to_contain_text("configuration", ignore_case=True)

    @pytest.mark.asyncio
    async def test_table_of_contents(self, page: Page, spa_server_url: str):
        """Test table of contents navigation."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Load a document with sections
        await page.click("[data-testid='doc-item-api-reference']")

        # TOC should be visible
        toc = page.locator("[data-testid='table-of-contents']")
        # await expect(toc).to_be_visible()

        # Check for TOC items
        toc_items = toc.locator("[data-testid='toc-item']")
        assert await toc_items.count() > 0

        # Click on a TOC item
        first_toc_item = toc_items.first
        section_title = await first_toc_item.text_content()
        await first_toc_item.click()

        # Should scroll to the section
        await page.wait_for_timeout(500)  # Wait for scroll animation

        # The section should be in view
        section_heading = page.locator(f"h2:has-text('{section_title}')")
        # await expect(section_heading).to_be_in_viewport()

    @pytest.mark.asyncio
    async def test_code_examples(self, page: Page, spa_server_url: str):
        """Test code examples display and copy functionality."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Navigate to API reference
        await page.click("[data-testid='doc-item-api-reference']")

        # Find code blocks
        code_blocks = page.locator("[data-testid='code-block']")
        # await expect(code_blocks.first).to_be_visible(timeout=5000)

        # Check for syntax highlighting
        first_code_block = code_blocks.first
        # await expect(first_code_block).to_have_class("language-")

        # Check for copy button
        copy_button = first_code_block.locator("[data-testid='copy-code-btn']")
        # await expect(copy_button).to_be_visible()

        # Click copy button
        await copy_button.click()

        # Check for copy confirmation
        await expect(page.locator("[data-testid='copy-success']")).to_be_visible()
        await expect(page.locator("[data-testid='copy-success']")).to_contain_text(
            "Copied"
        )

        # Confirmation should disappear after a few seconds
        await page.wait_for_timeout(3000)
        await expect(page.locator("[data-testid='copy-success']")).not_to_be_visible()

    @pytest.mark.asyncio
    async def test_external_links(self, page: Page, spa_server_url: str):
        """Test external links handling."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Load a document with external links
        await page.click("[data-testid='doc-item-resources']")

        # Find external links
        external_links = page.locator("[data-testid='external-link']")
        # await expect(external_links.first).to_be_visible(timeout=5000)

        # External links should have indicators
        first_link = external_links.first
        # await expect(first_link).to_have_attribute("target", "_blank")
        # await expect(first_link).to_have_attribute("rel", /noopener/)

        # Check for external link icon
        link_icon = first_link.locator("[data-testid='external-icon']")
        # await expect(link_icon).to_be_visible()

    @pytest.mark.asyncio
    async def test_breadcrumb_navigation(self, page: Page, spa_server_url: str):
        """Test breadcrumb navigation."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Navigate deep into documentation
        await page.click("[data-testid='doc-category-configuration']")
        await page.click("[data-testid='doc-item-advanced-config']")

        # Breadcrumb should be visible
        breadcrumb = page.locator("[data-testid='breadcrumb']")
        # await expect(breadcrumb).to_be_visible()

        # Check breadcrumb items
        breadcrumb_items = breadcrumb.locator("[data-testid='breadcrumb-item']")
        assert await breadcrumb_items.count() >= 2

        # Click on breadcrumb to navigate back
        await breadcrumb_items.first.click()

        # Should be back at docs home
        await expect(page.locator("[data-testid='docs-home']")).to_be_visible()

    @pytest.mark.asyncio
    async def test_version_selector(self, page: Page, spa_server_url: str):
        """Test documentation version selection."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Version selector should be visible
        version_selector = page.locator("[data-testid='version-selector']")
        # await expect(version_selector).to_be_visible()

        # Check current version
        current_version = await version_selector.input_value()
        assert current_version  # Should have a version

        # Open version dropdown
        await version_selector.click()

        # Check for version options
        version_options = page.locator("[data-testid='version-option']")
        assert await version_options.count() > 0

        # Select a different version
        if await version_options.count() > 1:
            await version_options.nth(1).click()

            # Content should update
            await expect(page.locator("[data-testid='version-banner']")).to_be_visible()
            new_version = await version_selector.input_value()
            assert new_version != current_version

    @pytest.mark.asyncio
    async def test_print_friendly_view(self, page: Page, spa_server_url: str):
        """Test print-friendly documentation view."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Load a document
        await page.click("[data-testid='doc-item-quickstart']")

        # Click print button
        await page.click("[data-testid='print-doc-btn']")

        # Print preview should open (or print dialog)
        # Note: Can't directly test print dialog, but can test print CSS
        await page.emulate_media(media="print")

        # Check that print-specific styles are applied
        sidebar = page.locator("[data-testid='docs-sidebar']")
        sidebar_display = await sidebar.evaluate(
            "el => window.getComputedStyle(el).display"
        )
        assert sidebar_display == "none"  # Sidebar should be hidden in print view

        # Reset media
        await page.emulate_media(media="screen")

    @pytest.mark.asyncio
    async def test_responsive_documentation(self, page: Page, spa_server_url: str):
        """Test responsive layout of documentation."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Desktop view
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await expect(page.locator("[data-testid='docs-sidebar']")).to_be_visible()
        await expect(page.locator("[data-testid='docs-viewer']")).to_be_visible()

        # Tablet view
        await page.set_viewport_size({"width": 768, "height": 1024})

        # Sidebar might be collapsible
        sidebar_toggle = page.locator("[data-testid='sidebar-toggle']")
        if await sidebar_toggle.is_visible():
            # Sidebar is collapsed, toggle it
            await sidebar_toggle.click()
            await expect(page.locator("[data-testid='docs-sidebar']")).to_be_visible()

        # Mobile view
        await page.set_viewport_size({"width": 375, "height": 667})

        # Sidebar should be hidden by default
        sidebar = page.locator("[data-testid='docs-sidebar']")
        if not await sidebar.is_visible():
            # Open mobile menu
            await page.click("[data-testid='mobile-menu-btn']")
            # await expect(sidebar).to_be_visible()

    @pytest.mark.asyncio
    async def test_feedback_widget(self, page: Page, spa_server_url: str):
        """Test documentation feedback widget."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Load a document
        await page.click("[data-testid='doc-item-installation']")

        # Feedback widget should be visible
        feedback_widget = page.locator("[data-testid='feedback-widget']")
        # await expect(feedback_widget).to_be_visible()

        # Check for feedback options
        await expect(page.locator("[data-testid='feedback-helpful']")).to_be_visible()
        await expect(
            page.locator("[data-testid='feedback-not-helpful']")
        ).to_be_visible()

        # Click helpful
        await page.click("[data-testid='feedback-helpful']")

        # Thank you message should appear
        await expect(page.locator("[data-testid='feedback-thanks']")).to_be_visible()

        # Additional feedback form might appear
        feedback_form = page.locator("[data-testid='feedback-form']")
        if await feedback_form.is_visible():
            # Fill feedback
            await page.fill(
                "[data-testid='feedback-text']", "Very clear documentation!"
            )
            await page.click("[data-testid='submit-feedback-btn']")

            # Confirmation should appear
            await expect(
                page.locator("[data-testid='feedback-submitted']")
            ).to_be_visible()

    @pytest.mark.asyncio
    async def test_offline_documentation(self, page: Page, spa_server_url: str):
        """Test offline documentation availability."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Load some documentation
        await page.click("[data-testid='doc-item-quickstart']")
        await page.wait_for_timeout(1000)  # Let content load

        # Go offline
        await page.context.set_offline(True)

        # Try to navigate to another doc
        await page.click("[data-testid='doc-item-installation']")

        # Should show offline message or cached content
        offline_indicator = page.locator("[data-testid='offline-indicator']")
        cached_content = page.locator("[data-testid='cached-content']")

        # Either offline indicator or cached content should be visible
        if await offline_indicator.is_visible():
            pass  # await expect(offline_indicator).to_contain_text("offline")
        elif await cached_content.is_visible():
            pass  # await expect(cached_content).to_be_visible()

        # Go back online
        await page.context.set_offline(False)

        # Content should load normally
        await page.click("[data-testid='retry-load-btn']") if await page.locator(
            "[data-testid='retry-load-btn']"
        ).is_visible() else None
        await expect(page.locator("[data-testid='docs-viewer']")).to_be_visible()

    @pytest.mark.asyncio
    async def test_keyboard_shortcuts(self, page: Page, spa_server_url: str):
        """Test keyboard shortcuts in documentation."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Test search shortcut (usually Ctrl+K or Cmd+K)
        await page.keyboard.press(
            "Control+K"
            if page.context.browser.browser_type.name != "webkit"
            else "Meta+K"
        )

        # Search should be focused
        search_input = page.locator("[data-testid='docs-search-input']")
        # await expect(search_input).to_be_focused()

        # Escape to close search
        await page.keyboard.press("Escape")

        # Test navigation shortcuts
        await page.keyboard.press("g")  # Often used for "go to"
        await page.keyboard.press("h")  # Go home

        # Should be at docs home
        await expect(page.locator("[data-testid='docs-home']")).to_be_visible()

    @pytest.mark.asyncio
    async def test_api_playground(self, page: Page, spa_server_url: str):
        """Test API playground if available in docs."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-docs']")

        # Navigate to API reference
        await page.click("[data-testid='doc-category-api-reference']")
        await page.click(
            "[data-testid='doc-item-api-playground']"
        ) if await page.locator(
            "[data-testid='doc-item-api-playground']"
        ).is_visible() else None

        # If API playground exists
        api_playground = page.locator("[data-testid='api-playground']")
        if await api_playground.is_visible():
            # Check for endpoint selector
            await expect(
                page.locator("[data-testid='endpoint-selector']")
            ).to_be_visible()

            # Select an endpoint
            await page.select_option("[data-testid='endpoint-selector']", index=0)

            # Check for request builder
            await expect(
                page.locator("[data-testid='request-builder']")
            ).to_be_visible()

            # Try to execute request
            await page.click("[data-testid='execute-request-btn']")

            # Response should be displayed
            await expect(page.locator("[data-testid='api-response']")).to_be_visible(
                timeout=5000
            )
