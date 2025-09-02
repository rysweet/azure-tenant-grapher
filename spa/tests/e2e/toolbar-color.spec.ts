import { test, expect } from '@playwright/test';

test.describe('Toolbar Background Color', () => {
  test('toolbar should have black background', async ({ page }) => {
    // Connect to running app
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // Wait for the AppBar to be visible
    const appBar = page.locator('.MuiAppBar-root').first();
    await expect(appBar).toBeVisible();

    // Get the computed background color
    const backgroundColor = await appBar.evaluate((element) => {
      const styles = window.getComputedStyle(element);
      return styles.backgroundColor;
    });

    console.log(`Actual toolbar background color: ${backgroundColor}`);

    // Check if it's black (rgb(0, 0, 0) or #000000)
    // This test will FAIL if the toolbar is not black
    expect(backgroundColor).toBe('rgb(0, 0, 0)');

    // Also check that there's no background image/gradient
    const backgroundImage = await appBar.evaluate((element) => {
      const styles = window.getComputedStyle(element);
      return styles.backgroundImage;
    });

    console.log(`Actual toolbar background image: ${backgroundImage}`);
    expect(backgroundImage).toBe('none');

    // Check the Toolbar inside AppBar as well
    const toolbar = page.locator('.MuiToolbar-root').first();
    await expect(toolbar).toBeVisible();

    const toolbarBgColor = await toolbar.evaluate((element) => {
      const styles = window.getComputedStyle(element);
      return styles.backgroundColor;
    });

    console.log(`Actual inner toolbar background color: ${toolbarBgColor}`);

    // Toolbar should either be black or transparent (inheriting from AppBar)
    expect(['rgb(0, 0, 0)', 'rgba(0, 0, 0, 0)', 'transparent']).toContain(toolbarBgColor);
  });

  test('take screenshot of current toolbar state', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // Take a screenshot of just the toolbar area
    const appBar = page.locator('.MuiAppBar-root').first();
    await appBar.screenshot({
      path: 'screenshots/toolbar-actual-color.png',
      animations: 'disabled'
    });

    console.log('Screenshot saved to screenshots/toolbar-actual-color.png');
  });
});
