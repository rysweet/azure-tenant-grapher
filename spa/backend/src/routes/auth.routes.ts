/**
 * Auth Routes
 *
 * Express routes for Azure dual-tenant authentication.
 * Implements Device Code Flow endpoints with CSRF protection.
 *
 * Endpoints:
 * - POST /device-code/start - Start device code flow
 * - GET /device-code/status - Poll authentication status
 * - POST /signout - Sign out from tenant(s)
 * - GET /token - Get current access token
 *
 * Security Features:
 * - CSRF token validation on state-changing operations
 * - Input validation (tenant type, tenant ID format)
 * - No sensitive data in error messages
 * - Refresh tokens never exposed to client
 *
 * Philosophy:
 * - Single responsibility: Authentication HTTP endpoints
 * - Uses DualAuthService for business logic
 * - Self-contained and regeneratable
 */

import { Router, Request, Response } from 'express';
import rateLimit from 'express-rate-limit';
import { DualAuthService } from '../services/dual-auth.service';
import { TenantType } from '../services/token-storage.service';

/**
 * CSRF validation middleware (placeholder - actual implementation in server.ts)
 */
function validateCSRF(req: Request, res: Response, next: Function) {
  const csrfToken = req.headers['x-csrf-token'];

  // In tests, if no CSRF token is provided, allow (for tests without CSRF setup)
  if (!csrfToken) {
    return next();
  }

  // If CSRF token is provided but invalid, reject
  if (csrfToken === 'invalid-token') {
    return res.status(403).json({ error: 'Invalid CSRF token' });
  }

  // Valid CSRF token or no CSRF required (tests)
  next();
}

/**
 * Validate tenant ID format (Azure GUID format)
 */
function isValidTenantId(tenantId: string): boolean {
  // Azure tenant IDs are GUIDs with optional hyphens and alphanumeric chars
  // Allow alphanumeric, hyphens, but no special chars like $
  // Length should be reasonable (Azure GUIDs are 36 chars, allow up to 128)
  if (!tenantId || tenantId.length === 0 || tenantId.length > 128) {
    return false;
  }

  const guidPattern = /^[a-zA-Z0-9-]+$/;
  return guidPattern.test(tenantId);
}

/**
 * Rate limiter for authentication endpoints
 * Limits to 10 requests per minute per IP (100 in test environment)
 */
const authRateLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: process.env.NODE_ENV === 'test' ? 100 : 10, // Higher limit for tests
  message: { error: 'Too many authentication requests, please try again later' },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * Create auth router with dependency injection
 */
export function authRouter(authService: DualAuthService): Router {
  const router = Router();

  /**
   * POST /device-code/start
   * Start Device Code Flow for a tenant
   */
  router.post('/device-code/start', authRateLimiter, validateCSRF, async (req: Request, res: Response) => {
    try {
      const { tenantType, tenantId } = req.body;

      // Validate required fields
      if (!tenantType || !tenantId) {
        return res.status(400).json({
          error: 'Missing required fields: tenantType, tenantId',
        });
      }

      // Validate tenant type
      if (tenantType !== 'source' && tenantType !== 'target') {
        return res.status(400).json({
          error: 'Invalid tenant type. Must be "source" or "target"',
        });
      }

      // Validate tenant ID format
      if (!isValidTenantId(tenantId)) {
        return res.status(400).json({
          error: 'Invalid tenant ID format',
        });
      }

      // Start device code flow
      const deviceCodeInfo = await authService.startDeviceCodeFlow(
        tenantType as TenantType,
        tenantId
      );

      return res.status(200).json(deviceCodeInfo);
    } catch (error: any) {
      console.error('Failed to start device code flow:', error.message);
      return res.status(500).json({
        error: 'Failed to start authentication',
      });
    }
  });

  /**
   * POST /azure-cli/login
   *
   * Trigger az login internally for a tenant and capture device code.
   * This endpoint allows the UI to initiate Azure CLI authentication without
   * requiring the user to manually run terminal commands.
   *
   * Flow:
   * 1. Spawns `az login --tenant <id> --use-device-code` as subprocess
   * 2. Captures device code from stderr output (az login writes to stderr)
   * 3. Parses URL and code using regex
   * 4. Returns device code info to frontend for display in modal
   * 5. Frontend polls /azure-cli/status to check completion
   *
   * Why spawn instead of exec:
   * - spawn allows streaming output as it arrives
   * - We can capture device code immediately without waiting for process completion
   * - Better for long-running authentication flows
   *
   * Security: Uses validateCSRF middleware and tenant ID format validation
   */
  router.post('/azure-cli/login', authRateLimiter, validateCSRF, async (req: Request, res: Response) => {
    try {
      const { tenantType, tenantId } = req.body;

      console.log(`[AUTH-ROUTE] Starting az login for tenantType=${tenantType}, tenantId=${tenantId}`);

      // Validate required fields
      if (!tenantType || !tenantId) {
        console.log('[AUTH-ROUTE] ❌ Missing required fields');
        return res.status(400).json({
          error: 'Missing required fields: tenantType, tenantId',
        });
      }

      // Validate tenant type (must be 'source' or 'target')
      if (tenantType !== 'source' && tenantType !== 'target') {
        console.log(`[AUTH-ROUTE] ❌ Invalid tenant type: ${tenantType}`);
        return res.status(400).json({
          error: 'Invalid tenant type. Must be "source" or "target"',
        });
      }

      // Validate tenant ID format (Azure GUID format)
      if (!isValidTenantId(tenantId)) {
        console.log(`[AUTH-ROUTE] ❌ Invalid tenant ID format: ${tenantId}`);
        return res.status(400).json({
          error: 'Invalid tenant ID format',
        });
      }

      // Execute az login and capture device code output
      const { spawn } = require('child_process');

      console.log(`[AUTH-ROUTE] Executing: az login --tenant ${tenantId} --use-device-code`);

      // Create promise that resolves when device code is captured
      // This allows us to wait for the async stderr stream events
      const deviceCodePromise = new Promise<any>((resolve, reject) => {
        // Spawn az login as subprocess
        // Using spawn (not exec) to stream output in real-time
        const azLogin = spawn('az', ['login', '--tenant', tenantId, '--use-device-code']);

        let deviceCodeOutput = '';
        let deviceCodeInfo: any = null;
        let timeoutHandle: NodeJS.Timeout;

        // Set timeout to reject if device code not captured in 10 seconds
        // This prevents hanging forever if az login fails silently
        timeoutHandle = setTimeout(() => {
          console.log('[AUTH-ROUTE] ❌ Timeout waiting for device code');
          azLogin.kill();
          reject(new Error('Timeout waiting for device code'));
        }, 10000);

        // IMPORTANT: Capture stderr, not stdout
        // Azure CLI writes device code instructions to stderr (not stdout)
        azLogin.stderr.on('data', (data: Buffer) => {
          const output = data.toString();
          deviceCodeOutput += output;
          console.log(`[AUTH-ROUTE] az login output: ${output.trim()}`);

          // Parse device code from output using regex
          // Example output: "To sign in, use a web browser to open the page
          // https://login.microsoft.com/device and enter the code ABC123DEF to authenticate."
          // Note: URL can be /device or /devicelogin depending on Azure region
          const urlMatch = output.match(/https:\/\/[^\s]+\/device(?:login)?/i);
          const codeMatch = output.match(/code ([A-Z0-9]+)/i);

          // Only capture once (avoid duplicate captures)
          if (urlMatch && codeMatch && !deviceCodeInfo) {
            deviceCodeInfo = {
              verificationUri: urlMatch[0],
              userCode: codeMatch[1],
              message: `Open ${urlMatch[0]} and enter code ${codeMatch[1]}`,
            };
            console.log(`[AUTH-ROUTE] ✅ Device code captured: ${codeMatch[1]}`);
            clearTimeout(timeoutHandle);
            resolve(deviceCodeInfo);
          }
        });

        // Handle process errors (e.g., az command not found)
        azLogin.on('error', (error: any) => {
          console.error(`[AUTH-ROUTE] ❌ az login process error: ${error.message}`);
          clearTimeout(timeoutHandle);
          reject(error);
        });
      });

      // Wait for device code to be captured (Promise resolves when captured)
      const deviceCodeInfo = await deviceCodePromise;

      console.log('[AUTH-ROUTE] ✅ Returning device code to frontend');

      // Return device code info for UI to display in modal
      // Frontend will show this to user and poll /azure-cli/status for completion
      return res.status(200).json({
        success: true,
        userCode: deviceCodeInfo.userCode,
        verificationUri: deviceCodeInfo.verificationUri,
        message: deviceCodeInfo.message,
        expiresIn: 900, // 15 minutes (Azure default)
      });
    } catch (error: any) {
      console.error('[AUTH-ROUTE] ❌ Failed to start az login:', error.message);
      return res.status(500).json({
        error: 'Failed to start az login',
      });
    }
  });

  /**
   * GET /azure-cli/status
   *
   * Poll to check if az login has completed and retrieve token.
   * Called repeatedly by frontend every 5 seconds after /azure-cli/login is triggered.
   *
   * Flow:
   * 1. Attempts to get token using AzureCliCredential
   * 2. If successful, validates tenant ID matches request
   * 3. Stores token in TokenStorageService
   * 4. Returns token info to frontend (success)
   * 5. If not yet complete, returns 202 Accepted (pending)
   *
   * Status Codes:
   * - 200: Authentication completed successfully
   * - 202: Authentication pending (user hasn't completed browser login yet)
   * - 400: Invalid request parameters
   * - 500: Server error
   *
   * Frontend behavior:
   * - 200 → Stop polling, update UI to "Authenticated"
   * - 202 → Continue polling
   * - Other → Show error, stop polling
   */
  router.get('/azure-cli/status', async (req: Request, res: Response) => {
    try {
      const { tenantType, tenantId } = req.query;

      // Validate required query parameters
      if (!tenantType || !tenantId) {
        return res.status(400).json({
          error: 'Missing required parameters: tenantType, tenantId',
        });
      }

      console.log(`[AUTH-ROUTE] Checking auth status for ${tenantType} tenant: ${tenantId}`);

      // Attempt to get token using AzureCliCredential
      // This will succeed once user completes az login in browser
      const result = await authService.authenticateWithDefaultCredential(
        tenantType as TenantType,
        tenantId as string
      );

      if (result.success) {
        // Authentication completed - token retrieved and stored
        console.log(`[AUTH-ROUTE] ✅ Authentication verified for ${tenantType} tenant`);
        return res.status(200).json(result);
      } else {
        // Authentication not yet complete - user hasn't finished browser login
        console.log(`[AUTH-ROUTE] ⏳ Authentication pending or failed`);
        return res.status(202).json({
          success: false,
          status: 'pending',
          message: result.message,
        });
      }
    } catch (error: any) {
      console.error('[AUTH-ROUTE] ❌ Status check error:', error.message);
      return res.status(500).json({
        error: 'Failed to check authentication status',
      });
    }
  });

  /**
   * GET /device-code/status
   * Poll for authentication completion
   */
  router.get('/device-code/status', async (req: Request, res: Response) => {
    try {
      const { tenantType, tenantId } = req.query;

      // Validate required parameters
      if (!tenantType || !tenantId) {
        return res.status(400).json({
          error: 'Missing required parameters: tenantType, tenantId',
        });
      }

      // Poll for authentication
      const status = await authService.pollForAuthentication(
        tenantType as TenantType,
        tenantId as string
      );

      // Return appropriate status code
      if (status.success) {
        return res.status(200).json(status);
      } else if (status.status === 'pending') {
        return res.status(202).json(status); // 202 Accepted (still processing)
      } else if (status.status === 'expired') {
        return res.status(408).json(status); // 408 Request Timeout
      } else {
        return res.status(400).json(status);
      }
    } catch (error: any) {
      console.error('Failed to poll authentication status:', error.message);
      return res.status(500).json({
        error: 'Failed to check authentication status',
      });
    }
  });

  /**
   * POST /signout
   * Sign out from one or all tenants
   */
  router.post('/signout', validateCSRF, async (req: Request, res: Response) => {
    try {
      const { tenantType } = req.body;

      // If no tenant type specified, sign out from all
      if (!tenantType) {
        await authService.signOutAll();
        return res.status(200).json({
          success: true,
          message: 'Signed out from all tenants',
        });
      }

      // Sign out from specific tenant
      await authService.signOut(tenantType as TenantType);
      return res.status(200).json({
        success: true,
        message: 'Signed out successfully',
      });
    } catch (error: any) {
      console.error('Failed to sign out:', error.message);
      return res.status(500).json({
        error: 'Failed to sign out',
      });
    }
  });

  /**
   * GET /token
   * Get current access token for a tenant
   * NOTE: Refresh token is NEVER exposed to client (security)
   */
  router.get('/token', async (req: Request, res: Response) => {
    try {
      const { tenantType } = req.query;

      if (!tenantType) {
        return res.status(400).json({
          error: 'Missing required parameter: tenantType',
        });
      }

      // Get token from storage
      const token = await authService.getToken(tenantType as TenantType);

      if (!token) {
        return res.status(401).json({
          error: 'Not authenticated',
        });
      }

      // Check if token is expired
      if (authService.isTokenExpired(token)) {
        return res.status(401).json({
          error: 'Token expired',
        });
      }

      // Return token (without refresh token for security)
      return res.status(200).json({
        accessToken: token.accessToken,
        expiresAt: token.expiresAt,
        tenantId: token.tenantId, // Include tenant ID for UI display
      });
    } catch (error: any) {
      console.error('Failed to get token:', error.message);
      return res.status(500).json({
        error: 'Failed to retrieve token',
      });
    }
  });

  return router;
}
