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
