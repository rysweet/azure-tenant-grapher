#!/usr/bin/env python
"""Test launching Electron with Playwright."""

import asyncio
from playwright.async_api import async_playwright, Playwright
import os


async def test_launch():
    """Test launching Electron app."""
    print("Testing Electron launch...")
    
    electron_path = os.path.abspath("spa/node_modules/.bin/electron")
    main_path = os.path.abspath("spa/dist/main/index.js")
    
    print(f"Electron: {electron_path}")
    print(f"Main: {main_path}")
    
    async with async_playwright() as p:
        print(f"Playwright attributes: {dir(p)}")
        
        # Check if _electron exists
        if hasattr(p, '_electron'):
            print("Found _electron attribute")
            electron = p._electron
        else:
            print("No _electron attribute found")
            
            # Try chromium with Electron executable
            print("Trying chromium launch with Electron...")
            browser = await p.chromium.launch(
                executable_path=electron_path,
                args=[main_path]
            )
            
            page = await browser.new_page()
            await page.wait_for_timeout(2000)
            
            # Take screenshot
            await page.screenshot(path="electron_test.png")
            print("Screenshot saved to electron_test.png")
            
            await browser.close()
            return
        
        # Launch with _electron if it exists
        app = await electron.launch(
            executable_path=electron_path,
            args=[main_path]
        )
        
        window = await app.first_window()
        await window.screenshot(path="electron_test.png")
        print("Screenshot saved!")
        
        await app.close()


if __name__ == "__main__":
    asyncio.run(test_launch())