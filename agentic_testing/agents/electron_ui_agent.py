"""Electron UI testing agent using Playwright."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright

from ..config import UIConfig
from ..models import AppState, TestInterface, TestStep
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ElectronUIAgent:
    """Agent responsible for Electron UI testing using Playwright."""

    def __init__(self, config: UIConfig):
        """
        Initialize UI testing agent.

        Args:
            config: UI configuration
        """
        self.config = config
        self.app_path = Path(config.app_path)
        self.screenshot_dir = Path(config.screenshot_dir)
        self.video_dir = Path(config.video_dir)
        self.viewport = config.viewport
        self.headless = config.headless
        self.slow_mo = config.slow_mo
        self.timeout = config.timeout

        self.playwright = None
        self.electron_app = None
        self.window = None

        # Create output directories
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)

    async def launch_application(self) -> bool:
        """
        Launch the Electron application.

        Returns:
            True if launched successfully
        """
        try:
            logger.info("Launching Electron application...")

            self.playwright = await async_playwright().start()

            # Launch Electron app
            self.electron_app = await self.playwright._electron.launch(
                executable_path=str(self.app_path),
                args=["--no-sandbox"] if self.headless else [],
                env={"NODE_ENV": "test", "TESTING": "true"},
            )

            # Get the first window
            self.window = await self.electron_app.first_window()

            # Set viewport size
            await self.window.set_viewport_size(
                width=self.viewport["width"], height=self.viewport["height"]
            )

            # Wait for app to be ready
            await self.window.wait_for_load_state("networkidle")

            logger.info("Electron application launched successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to launch Electron app: {e}")
            return False

    async def close_application(self):
        """Close the Electron application."""
        try:
            if self.electron_app:
                await self.electron_app.close()
            if self.playwright:
                await self.playwright.stop()

            logger.info("Electron application closed")

        except Exception as e:
            logger.error(f"Error closing Electron app: {e}")

    async def capture_state(self) -> AppState:
        """
        Capture current application state.

        Returns:
            AppState with current information
        """
        if not self.window:
            raise RuntimeError("Application not launched")

        timestamp = datetime.now()

        # Take screenshot
        screenshot_name = f"state_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
        screenshot_path = self.screenshot_dir / screenshot_name
        await self.window.screenshot(path=str(screenshot_path))

        # Get page title
        title = await self.window.title()

        # Get URL (for web content in Electron)
        url = self.window.url

        # Get accessibility tree
        accessibility_tree = await self.window.accessibility.snapshot()

        return AppState(
            timestamp=timestamp,
            interface=TestInterface.GUI,
            screenshot_path=str(screenshot_path),
            url=url,
            title=title,
            accessibility_tree=accessibility_tree,
        )

    async def execute_test_step(self, step: TestStep) -> Dict[str, Any]:
        """
        Execute a single UI test step.

        Args:
            step: Test step to execute

        Returns:
            Result dictionary with execution details
        """
        if not self.window:
            raise RuntimeError("Application not launched")

        try:
            result = {"success": True, "step": step}

            if step.action == "click":
                await self._handle_click(step)

            elif step.action == "type":
                await self._handle_type(step)

            elif step.action == "wait":
                await self._handle_wait(step)

            elif step.action == "verify":
                result["success"] = await self._handle_verify(step)

            elif step.action == "screenshot":
                screenshot_path = await self._take_screenshot(
                    step.description or "step"
                )
                result["screenshot"] = screenshot_path

            elif step.action == "navigate":
                await self._handle_navigate(step)

            else:
                logger.warning(f"Unsupported UI action: {step.action}")
                result["success"] = False
                result["error"] = f"Unsupported action: {step.action}"

            return result

        except Exception as e:
            logger.error(f"Error executing UI step: {e}")
            return {"success": False, "error": str(e), "step": step}

    async def _handle_click(self, step: TestStep):
        """Handle click action."""
        selector = step.target

        # Wait for element to be visible
        await self.window.wait_for_selector(
            selector, state="visible", timeout=step.timeout or self.timeout
        )

        # Click element
        await self.window.click(selector)

        # Wait for any animations
        if self.slow_mo:
            await asyncio.sleep(self.slow_mo / 1000)

    async def _handle_type(self, step: TestStep):
        """Handle type action."""
        selector = step.target
        text = step.value or ""

        # Wait for element to be visible
        await self.window.wait_for_selector(
            selector, state="visible", timeout=step.timeout or self.timeout
        )

        # Clear existing text and type new text
        await self.window.fill(selector, text)

    async def _handle_wait(self, step: TestStep):
        """Handle wait action."""
        if step.wait_for:
            # Wait for specific condition
            if step.wait_for.startswith("selector:"):
                selector = step.wait_for[9:]  # Remove "selector:" prefix
                await self.window.wait_for_selector(
                    selector, timeout=step.timeout or self.timeout
                )
            elif step.wait_for == "networkidle":
                await self.window.wait_for_load_state("networkidle")
            else:
                # Wait for specific duration
                wait_time = float(step.value or 1)
                await asyncio.sleep(wait_time)
        else:
            # Simple wait
            wait_time = float(step.value or 1)
            await asyncio.sleep(wait_time)

    async def _handle_verify(self, step: TestStep) -> bool:
        """Handle verify action."""
        if step.expected is None:
            return False

        if isinstance(step.expected, dict):
            # Verify multiple conditions
            for key, value in step.expected.items():
                if key == "text_content":
                    actual = await self.window.text_content(step.target)
                    if actual != value:
                        logger.error(
                            f"Text mismatch: expected '{value}', got '{actual}'"
                        )
                        return False

                elif key == "is_visible":
                    is_visible = await self.window.is_visible(step.target)
                    if is_visible != value:
                        logger.error(
                            f"Visibility mismatch: expected {value}, got {is_visible}"
                        )
                        return False

                elif key == "count":
                    elements = await self.window.query_selector_all(step.target)
                    if len(elements) != value:
                        logger.error(
                            f"Count mismatch: expected {value}, got {len(elements)}"
                        )
                        return False
            return True

        else:
            # Simple text verification
            actual = await self.window.text_content(step.target)
            return str(step.expected) in actual if actual else False

    async def _handle_navigate(self, step: TestStep):
        """Handle navigation action."""
        # For Electron apps, this might mean clicking on a tab or menu item
        await self.window.click(step.target)
        await self.window.wait_for_load_state("networkidle")

    async def _take_screenshot(self, name: str) -> str:
        """Take a screenshot."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = self.screenshot_dir / filename
        await self.window.screenshot(path=str(filepath))
        return str(filepath)

    async def click_tab(self, tab_name: str) -> bool:
        """
        Click on a specific tab in the application.

        Args:
            tab_name: Name of the tab to click

        Returns:
            True if successful
        """
        try:
            # Try different tab selectors
            selectors = [
                f"button:has-text('{tab_name}')",
                f"[role='tab']:has-text('{tab_name}')",
                f".tab:has-text('{tab_name}')",
                f"text={tab_name}",
            ]

            for selector in selectors:
                if await self.window.is_visible(selector):
                    await self.window.click(selector)
                    await self.window.wait_for_load_state("networkidle")
                    logger.info(f"Clicked on tab: {tab_name}")
                    return True

            logger.error(f"Tab not found: {tab_name}")
            return False

        except Exception as e:
            logger.error(f"Error clicking tab {tab_name}: {e}")
            return False

    async def get_visible_text(self) -> str:
        """
        Get all visible text on the current page.

        Returns:
            Visible text content
        """
        if not self.window:
            return ""

        try:
            return await self.window.inner_text("body")
        except Exception:
            return ""

    async def wait_for_element(
        self, selector: str, timeout: Optional[int] = None
    ) -> bool:
        """
        Wait for an element to appear.

        Args:
            selector: Element selector
            timeout: Timeout in milliseconds

        Returns:
            True if element found
        """
        try:
            await self.window.wait_for_selector(
                selector, timeout=timeout or self.timeout
            )
            return True
        except Exception:
            return False

    async def get_element_count(self, selector: str) -> int:
        """
        Get count of elements matching selector.

        Args:
            selector: Element selector

        Returns:
            Number of matching elements
        """
        if not self.window:
            return 0

        elements = await self.window.query_selector_all(selector)
        return len(elements)
