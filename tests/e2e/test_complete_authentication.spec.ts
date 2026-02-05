/**
 * End-to-End Tests for Complete Authentication Flow
 *
 * Testing Strategy:
 * - E2E tests (10% of test suite)
 * - Test complete user workflows from UI to backend to Python CLI
 * - Use Playwright for browser automation
 *
 * These tests will FAIL initially (TDD approach) until implementation is complete.
 */

import { test, expect, Page } from '@playwright/test';
import { spawn, ChildProcess } from 'child_process';

test.describe('Complete Dual Authentication E2E', () => {
  let backendProcess: ChildProcess;
  const backendUrl = 'http://localhost:3001';
  const sourceTenantId = 'e2e-source-tenant-12345';
  const targetTenantId = 'e2e-target-tenant-67890';

  test.beforeAll(async () => {
    // Start backend server
    backendProcess = spawn('npm', ['run', 'dev:backend'], {
      cwd: process.cwd(),
      env: { ...process.env, PORT: '3001' },
    });

    // Wait for backend to be ready
    await new Promise(resolve => setTimeout(resolve, 5000));
  });

  test.afterAll(async () => {
    // Cleanup backend
    if (backendProcess) {
      backendProcess.kill();
    }
  });

  test('E2E: Complete source tenant authentication flow', async ({ page }) => {
    // Step 1: Navigate to Auth tab
    await page.goto('http://localhost:5173'); // Vite dev server
    await page.click('text=Authentication');

    // Step 2: Verify initial state (not authenticated)
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Not Authenticated/i);

    // Step 3: Click Sign In for source tenant
    await page.click('[data-testid="source-signin-button"]');

    // Step 4: Verify modal appears with device code
    await expect(page.locator('role=dialog')).toBeVisible();
    await expect(page.locator('[data-testid="device-code"]')).toBeVisible();

    // Get device code from modal
    const deviceCode = await page.locator('[data-testid="device-code"]').textContent();
    expect(deviceCode).toMatch(/^[A-Z0-9]{4}-[A-Z0-9]{4}$/); // Format: ABCD-1234

    // Step 5: Verify verification URL is displayed
    const verificationLink = page.locator('role=link[name*="devicelogin"]');
    await expect(verificationLink).toBeVisible();
    await expect(verificationLink).toHaveAttribute('href', 'https://microsoft.com/devicelogin');

    // Step 6: Verify QR code is displayed
    await expect(page.locator('[data-testid="qr-code"]')).toBeVisible();

    // Step 7: Verify copy button works
    await page.click('[data-testid="copy-code-button"]');
    await expect(page.locator('text=Copied!')).toBeVisible({ timeout: 2000 });

    // Step 8: Simulate authentication completion (mock)
    // In real E2E, this would involve opening a new tab and completing device code flow
    // For this test, we'll mock the backend response

    // Wait for polling to detect authentication
    await page.waitForTimeout(6000); // Wait for polling interval

    // Step 9: Verify modal closes and status updates
    await expect(page.locator('role=dialog')).not.toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Authenticated/i);

    // Step 10: Verify token expiration time is shown
    await expect(page.locator('[data-testid="source-expires"]')).toContainText(/Expires in/i);

    // Step 11: Verify scanning is enabled
    await expect(page.locator('[data-testid="scan-enabled"]')).toBeVisible();
  });

  test('E2E: Complete dual tenant authentication flow', async ({ page }) => {
    // Step 1: Navigate to Auth tab
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');

    // Step 2: Authenticate source tenant
    await page.click('[data-testid="source-signin-button"]');
    await expect(page.locator('role=dialog')).toBeVisible();

    // Wait for authentication completion (mocked)
    await page.waitForTimeout(6000);
    await expect(page.locator('role=dialog')).not.toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Authenticated/i);

    // Step 3: Verify deployment still disabled (need target tenant)
    await expect(page.locator('[data-testid="deploy-disabled"]')).toBeVisible();

    // Step 4: Authenticate target tenant
    await page.click('[data-testid="target-signin-button"]');
    await expect(page.locator('role=dialog')).toBeVisible();

    // Wait for authentication completion (mocked)
    await page.waitForTimeout(6000);
    await expect(page.locator('role=dialog')).not.toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="target-status"]')).toHaveText(/Authenticated/i);

    // Step 5: Verify both scanning and deployment are enabled
    await expect(page.locator('[data-testid="scan-enabled"]')).toBeVisible();
    await expect(page.locator('[data-testid="deploy-enabled"]')).toBeVisible();
  });

  test('E2E: Sign out clears authentication', async ({ page }) => {
    // Step 1: Authenticate source tenant first
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');
    await page.click('[data-testid="source-signin-button"]');
    await page.waitForTimeout(6000);
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Authenticated/i);

    // Step 2: Click sign out
    await page.click('[data-testid="source-signout-button"]');

    // Step 3: Verify status updated
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Not Authenticated/i);

    // Step 4: Verify scanning disabled
    await expect(page.locator('[data-testid="scan-disabled"]')).toBeVisible();

    // Step 5: Verify token removed from backend
    const response = await page.request.get(`${backendUrl}/api/auth/token?tenantType=source`);
    expect(response.status()).toBe(401); // Unauthorized
  });

  test('E2E: Token expires and auto-refreshes', async ({ page }) => {
    // Step 1: Authenticate with short-lived token (mocked)
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');
    await page.click('[data-testid="source-signin-button"]');

    // Mock backend to return token expiring in 4 minutes
    await page.route('**/api/auth/device-code/status*', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          accessToken: 'mock-token',
          expiresAt: Date.now() + 240000, // 4 minutes
        }),
      });
    });

    await page.waitForTimeout(6000);
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Authenticated/i);

    // Step 2: Wait for refresh timer (4 minutes)
    await page.waitForTimeout(240000);

    // Step 3: Verify token refreshed
    const tokenResponse = await page.request.get(`${backendUrl}/api/auth/token?tenantType=source`);
    const tokenData = await tokenResponse.json();
    expect(tokenData.accessToken).toBe('refreshed-token');

    // Step 4: Verify UI still shows authenticated
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Authenticated/i);
  });

  test('E2E: Python CLI uses token from backend', async ({ page }) => {
    // Step 1: Authenticate source tenant
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');
    await page.click('[data-testid="source-signin-button"]');
    await page.waitForTimeout(6000);
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Authenticated/i);

    // Step 2: Get token from backend API
    const tokenResponse = await page.request.get(`${backendUrl}/api/auth/token?tenantType=source`);
    const tokenData = await tokenResponse.json();
    const accessToken = tokenData.accessToken;

    expect(accessToken).toBeDefined();
    expect(accessToken.length).toBeGreaterThan(50);

    // Step 3: Trigger scan operation (which invokes Python CLI)
    await page.click('text=Scan');
    await page.click('[data-testid="start-scan-button"]');

    // Step 4: Verify Python CLI receives token via environment variable
    // (This would be verified through logs or CLI output)
    await expect(page.locator('[data-testid="scan-status"]')).toHaveText(/Running/i);

    // Wait for scan to complete
    await page.waitForSelector('[data-testid="scan-status"]:has-text("Complete")', { timeout: 30000 });

    // Step 5: Verify scan succeeded (token was accepted by Azure)
    await expect(page.locator('[data-testid="scan-result"]')).toContainText(/Success/i);
  });

  test('E2E: Cross-tenant deployment flow', async ({ page }) => {
    // Step 1: Authenticate both tenants
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');

    // Source tenant
    await page.click('[data-testid="source-signin-button"]');
    await page.waitForTimeout(6000);
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Authenticated/i);

    // Target tenant
    await page.click('[data-testid="target-signin-button"]');
    await page.waitForTimeout(6000);
    await expect(page.locator('[data-testid="target-status"]')).toHaveText(/Authenticated/i);

    // Step 2: Perform scan on source tenant
    await page.click('text=Scan');
    await page.click('[data-testid="start-scan-button"]');
    await page.waitForSelector('[data-testid="scan-status"]:has-text("Complete")', { timeout: 30000 });

    // Step 3: Navigate to deployment tab
    await page.click('text=Deploy');

    // Step 4: Verify deployment is enabled
    await expect(page.locator('[data-testid="deploy-button"]')).toBeEnabled();

    // Step 5: Start deployment
    await page.click('[data-testid="deploy-button"]');

    // Step 6: Verify deployment uses both tokens
    await expect(page.locator('[data-testid="deploy-status"]')).toHaveText(/Deploying/i);

    // Step 7: Wait for deployment to complete
    await page.waitForSelector('[data-testid="deploy-status"]:has-text("Complete")', { timeout: 60000 });

    // Step 8: Verify deployment succeeded
    await expect(page.locator('[data-testid="deploy-result"]')).toContainText(/Success/i);
  });

  test('E2E: Authentication timeout handling', async ({ page }) => {
    // Step 1: Start authentication
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');
    await page.click('[data-testid="source-signin-button"]');

    await expect(page.locator('role=dialog')).toBeVisible();

    // Step 2: Mock backend to return expiration
    await page.route('**/api/auth/device-code/status*', route => {
      route.fulfill({
        status: 408, // Request Timeout
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          status: 'expired',
          message: 'Device code has expired',
        }),
      });
    });

    // Step 3: Wait for timeout (15 minutes, or mock sooner)
    await page.waitForTimeout(900000); // 15 minutes

    // Step 4: Verify modal closes with timeout message
    await expect(page.locator('role=dialog')).not.toBeVisible();
    await expect(page.locator('[data-testid="error-message"]')).toHaveText(/expired/i);

    // Step 5: Verify status remains "Not Authenticated"
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Not Authenticated/i);
  });

  test('E2E: Security - Token not exposed in browser console', async ({ page }) => {
    // Step 1: Authenticate
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');
    await page.click('[data-testid="source-signin-button"]');
    await page.waitForTimeout(6000);

    // Step 2: Check browser console logs
    const consoleLogs: string[] = [];
    page.on('console', msg => consoleLogs.push(msg.text()));

    // Trigger some actions
    await page.click('text=Scan');
    await page.waitForTimeout(2000);

    // Step 3: Verify token not in console
    const tokenInLogs = consoleLogs.some(log =>
      log.includes('access') && log.includes('token') && log.length > 50
    );
    expect(tokenInLogs).toBe(false);
  });

  test('E2E: Security - Token not exposed in network traffic', async ({ page }) => {
    const networkRequests: any[] = [];

    // Capture network requests
    page.on('request', request => {
      networkRequests.push({
        url: request.url(),
        postData: request.postData(),
      });
    });

    // Step 1: Authenticate
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');
    await page.click('[data-testid="source-signin-button"]');
    await page.waitForTimeout(6000);

    // Step 2: Check network requests
    const tokenInRequests = networkRequests.some(req => {
      if (!req.url.includes('/api/auth/')) return false;
      const postData = req.postData || '';
      // Token should only appear in specific auth endpoints, not leaked elsewhere
      return postData.includes('accessToken') && !req.url.includes('/api/auth/token');
    });

    expect(tokenInRequests).toBe(false);
  });
});

test.describe('Error Scenarios E2E', () => {
  test('E2E: Network error during authentication', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');

    // Mock network failure
    await page.route('**/api/auth/device-code/start', route => {
      route.abort('failed');
    });

    await page.click('[data-testid="source-signin-button"]');

    // Verify error message
    await expect(page.locator('[data-testid="error-message"]')).toHaveText(/network error/i);
    await expect(page.locator('[data-testid="source-status"]')).toHaveText(/Not Authenticated/i);
  });

  test('E2E: Invalid tenant ID', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text=Authentication');

    // Mock backend validation error
    await page.route('**/api/auth/device-code/start', route => {
      route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          error: 'Invalid tenant ID format',
        }),
      });
    });

    await page.click('[data-testid="source-signin-button"]');

    // Verify error message
    await expect(page.locator('[data-testid="error-message"]')).toHaveText(/Invalid tenant ID/i);
  });
});
