"""
Pytest configuration for SPA Tab E2E tests.
Provides shared fixtures and configuration for Playwright-based testing.
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, Generator

import pytest
import pytest_asyncio
from playwright.async_api import Browser, BrowserContext, Page, async_playwright


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def spa_server_url() -> str:
    """Get the SPA server URL from environment or use default."""
    return os.getenv("SPA_SERVER_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def websocket_url() -> str:
    """Get the WebSocket URL from environment or use default."""
    return os.getenv("WEBSOCKET_URL", "ws://localhost:3001")


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Get the test data directory."""
    return Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def electron_app_path() -> str:
    """Get the Electron app path from environment."""
    app_path = os.getenv("ELECTRON_APP_PATH")
    if not app_path:
        # Try to find the built Electron app
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "spa" / "dist" / "electron",
            Path(__file__).parent.parent.parent.parent / "spa" / "out",
        ]
        for path in possible_paths:
            if path.exists():
                app_path = str(path)
                break

    if not app_path:
        pytest.skip(
            "Electron app path not found. Set ELECTRON_APP_PATH environment variable."
        )

    return app_path


@pytest_asyncio.fixture(scope="session")
async def browser() -> AsyncGenerator[Browser, None]:
    """Create a Playwright browser instance."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        yield browser
        await browser.close()


@pytest_asyncio.fixture(scope="function")
async def browser_context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
    """Create a new browser context for each test."""
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )

    # Enable console log capturing
    context.on("console", lambda msg: print(f"Browser console: {msg.text}"))

    yield context
    await context.close()


@pytest_asyncio.fixture(scope="function")
async def page(browser_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """Create a new page for each test."""
    page = await browser_context.new_page()

    # Set default timeout
    page.set_default_timeout(30000)  # 30 seconds

    # Add custom data-testid attribute support
    await page.add_init_script("""
        // Add data-testid support for easier element selection
        window.testIdCounter = 0;
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach((node) => {
                        if (node.nodeType === Node.ELEMENT_NODE && !node.getAttribute('data-testid')) {
                            // Auto-add testid to common interactive elements
                            if (node.tagName && ['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'].includes(node.tagName)) {
                                node.setAttribute('data-testid', `auto-${node.tagName.toLowerCase()}-${window.testIdCounter++}`);
                            }
                        }
                    });
                }
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
    """)

    yield page


@pytest.fixture(scope="function")
def mock_azure_config() -> Dict[str, str]:
    """Provide mock Azure configuration for testing."""
    return {
        "tenant_id": "test-tenant-123",
        "client_id": "test-client-456",
        "client_secret": "test-secret-789",
        "subscription_id": "test-sub-abc",
    }


@pytest.fixture(scope="function")
def mock_neo4j_config() -> Dict[str, str]:
    """Provide mock Neo4j configuration for testing."""
    return {
        "uri": "bolt://localhost:7687",
        "username": "neo4j",
        "password": "test-password",
        "database": "neo4j",
    }


@pytest_asyncio.fixture(scope="function")
async def websocket_listener(websocket_url: str):
    """Create a WebSocket listener for capturing events during tests."""
    import websockets

    events = []

    async def listen():
        try:
            async with websockets.connect(websocket_url) as websocket:
                while True:
                    message = await websocket.recv()
                    events.append(json.loads(message))
        except Exception as e:
            print(f"WebSocket listener error: {e}")

    # Start listener in background
    task = asyncio.create_task(listen())

    yield events

    # Cancel listener task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.fixture(scope="function")
def spa_server(spa_server_url: str) -> Generator[str, None, None]:
    """Ensure SPA server is running for tests."""
    # Check if server is already running
    import requests

    try:
        response = requests.get(spa_server_url, timeout=2)
        if response.status_code == 200:
            yield spa_server_url
            return
    except (requests.RequestException, OSError):
        pass

    # Start the server if not running
    spa_dir = Path(__file__).parent.parent.parent.parent / "spa"
    process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=spa_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    max_attempts = 30
    for _ in range(max_attempts):
        try:
            response = requests.get(spa_server_url, timeout=2)
            if response.status_code == 200:
                break
        except (requests.RequestException, OSError):
            time.sleep(1)

    yield spa_server_url

    # Stop the server
    process.terminate()
    process.wait(timeout=5)


@pytest.fixture(autouse=True)
def test_environment_setup():
    """Set up test environment variables."""
    os.environ.setdefault("NODE_ENV", "test")
    os.environ.setdefault("LOG_LEVEL", "debug")
    yield
    # Cleanup if needed


@pytest.fixture
def assert_element_visible():
    """Helper fixture to assert element visibility."""

    async def _assert(page: Page, selector: str, timeout: int = 5000):
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            return True
        except Exception as e:
            pytest.fail(f"Element {selector} not visible: {e}")

    return _assert


@pytest.fixture
def assert_element_text():
    """Helper fixture to assert element text content."""

    async def _assert(
        page: Page, selector: str, expected_text: str, timeout: int = 5000
    ):
        try:
            element = await page.wait_for_selector(selector, timeout=timeout)
            actual_text = await element.text_content()
            assert expected_text in actual_text, (
                f"Expected '{expected_text}' in '{actual_text}'"
            )
            return True
        except Exception as e:
            pytest.fail(f"Text assertion failed for {selector}: {e}")

    return _assert


@pytest.fixture
def capture_screenshot():
    """Helper fixture to capture screenshots during tests."""
    screenshots_dir = Path(__file__).parent / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    async def _capture(page: Page, name: str):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = screenshots_dir / f"{name}_{timestamp}.png"
        await page.screenshot(path=str(filename))
        return filename

    return _capture
