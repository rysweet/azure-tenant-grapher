import { test } from '@playwright/test';

test('check toolbar actual color', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);

  // Wait for the app to actually render
  await page.waitForSelector('div:has-text("Azure Tenant Grapher")', { timeout: 10000 });

  // Find the element containing "Azure Tenant Grapher"
  const result = await page.evaluate(() => {
    const elements = document.querySelectorAll('*');
    const results = [];

    for (const el of elements) {
      if (el.textContent?.includes('Azure Tenant Grapher') &&
          !el.textContent.includes('v1.0.0')) {
        const styles = window.getComputedStyle(el);
        const parent = el.parentElement;
        const parentStyles = parent ? window.getComputedStyle(parent) : null;
        const grandparent = parent?.parentElement;
        const grandparentStyles = grandparent ? window.getComputedStyle(grandparent) : null;

        results.push({
          element: {
            tag: el.tagName,
            text: el.textContent?.substring(0, 50),
            bg: styles.backgroundColor,
            color: styles.color,
            classes: el.className
          },
          parent: parent ? {
            tag: parent.tagName,
            bg: parentStyles?.backgroundColor,
            classes: parent.className
          } : null,
          grandparent: grandparent ? {
            tag: grandparent.tagName,
            bg: grandparentStyles?.backgroundColor,
            classes: grandparent.className
          } : null
        });
      }
    }

    return results;
  });

  console.log('TOOLBAR COLOR DEBUG:');
  console.log(JSON.stringify(result, null, 2));

  // Also check for any element with black background
  const blackElements = await page.evaluate(() => {
    const elements = document.querySelectorAll('*');
    const blacks = [];

    for (const el of elements) {
      const styles = window.getComputedStyle(el);
      if (styles.backgroundColor === 'rgb(0, 0, 0)' ||
          styles.backgroundColor === '#000000') {
        blacks.push({
          tag: el.tagName,
          classes: el.className,
          text: el.textContent?.substring(0, 30)
        });
      }
    }

    return blacks;
  });

  console.log('\nELEMENTS WITH BLACK BACKGROUND:');
  console.log(JSON.stringify(blackElements, null, 2));
});
