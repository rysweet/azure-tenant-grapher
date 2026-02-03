/**
 * Integration Tests for Dual Authentication Flow
 *
 * Testing Strategy:
 * - Integration tests (30% of test suite)
 * - Test multiple components working together
 * - Test full authentication flow from frontend to backend
 *
 * These tests will FAIL initially (TDD approach) until implementation is complete.
 */

import request from 'supertest';
import express from 'express';
import { authRouter } from '../../spa/backend/src/routes/auth.routes';
import { DualAuthService } from '../../spa/backend/src/services/dual-auth.service';
import { TokenStorageService } from '../../spa/backend/src/services/token-storage.service';
import { DeviceCodeCredential } from '@azure/identity';

// Minimal mocking - test real integration
jest.mock('@azure/identity');
const mockDeviceCodeCredential = DeviceCodeCredential as jest.MockedClass<typeof DeviceCodeCredential>;

describe('Dual Authentication Flow - Integration Tests (30% coverage)', () => {
  let app: express.Application;
  let tokenStorage: TokenStorageService;
  let authService: DualAuthService;

  const sourceTenantId = 'source-tenant-integration-test';
  const targetTenantId = 'target-tenant-integration-test';
  const clientId = 'test-client-id';

  beforeEach(() => {
    // Create real instances (minimal mocking)
    const encryptionKey = 'test-encryption-key-32-bytes-long!';
    tokenStorage = new TokenStorageService(encryptionKey);
    authService = new DualAuthService(tokenStorage, clientId);

    // Setup Express app with real routes
    app = express();
    app.use(express.json());
    app.use('/api/auth', authRouter(authService));

    jest.clearAllMocks();
  });

  afterEach(async () => {
    // Cleanup - clear all tokens
    await tokenStorage.clearAllTokens();
  });

  describe('Complete Authentication Flow - Source Tenant', () => {
    it('should complete full authentication flow from start to token retrieval', async () => {
      // Step 1: Start device code flow
      const mockDeviceCodeInfo = {
        userCode: 'TEST1234',
        deviceCode: 'device-code-12345',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresOn: new Date(Date.now() + 900000),
        interval: 5,
        message: 'Enter code TEST1234',
      };

      mockDeviceCodeCredential.prototype.authenticate = jest.fn().mockResolvedValue({
        deviceCodeInfo: mockDeviceCodeInfo,
      });

      const startResponse = await request(app)
        .post('/api/auth/device-code/start')
        .send({
          tenantType: 'source',
          tenantId: sourceTenantId,
        })
        .expect(200);

      expect(startResponse.body.userCode).toBe('TEST1234');

      // Step 2: Poll for authentication (pending)
      mockDeviceCodeCredential.prototype.getToken = jest.fn().mockRejectedValue({
        name: 'CredentialUnavailableError',
        message: 'User has not authenticated',
      });

      const pendingResponse = await request(app)
        .get('/api/auth/device-code/status')
        .query({
          tenantType: 'source',
          tenantId: sourceTenantId,
        })
        .expect(202);

      expect(pendingResponse.body.status).toBe('pending');

      // Step 3: Poll for authentication (success)
      const mockToken = {
        token: 'integration-test-access-token',
        expiresOnTimestamp: Date.now() + 3600000,
      };

      mockDeviceCodeCredential.prototype.getToken = jest.fn().mockResolvedValue(mockToken);

      const successResponse = await request(app)
        .get('/api/auth/device-code/status')
        .query({
          tenantType: 'source',
          tenantId: sourceTenantId,
        })
        .expect(200);

      expect(successResponse.body.success).toBe(true);
      expect(successResponse.body.accessToken).toBe('integration-test-access-token');

      // Step 4: Verify token was stored
      const storedToken = await tokenStorage.getToken('source');
      expect(storedToken).not.toBeNull();
      expect(storedToken!.accessToken).toBe('integration-test-access-token');

      // Step 5: Retrieve token via API
      const tokenResponse = await request(app)
        .get('/api/auth/token')
        .query({ tenantType: 'source' })
        .expect(200);

      expect(tokenResponse.body.accessToken).toBe('integration-test-access-token');
    });
  });

  describe('Dual Tenant Authentication Flow', () => {
    it('should handle authentication for both source and target tenants', async () => {
      // Authenticate source tenant
      mockDeviceCodeCredential.prototype.authenticate = jest.fn().mockResolvedValue({
        deviceCodeInfo: {
          userCode: 'SOURCE123',
          deviceCode: 'source-device-code',
          verificationUri: 'https://microsoft.com/devicelogin',
          expiresOn: new Date(Date.now() + 900000),
          interval: 5,
          message: 'Enter code SOURCE123',
        },
      });

      const sourceStartResponse = await request(app)
        .post('/api/auth/device-code/start')
        .send({
          tenantType: 'source',
          tenantId: sourceTenantId,
        })
        .expect(200);

      expect(sourceStartResponse.body.userCode).toBe('SOURCE123');

      mockDeviceCodeCredential.prototype.getToken = jest.fn().mockResolvedValue({
        token: 'source-access-token',
        expiresOnTimestamp: Date.now() + 3600000,
      });

      await request(app)
        .get('/api/auth/device-code/status')
        .query({
          tenantType: 'source',
          tenantId: sourceTenantId,
        })
        .expect(200);

      // Authenticate target tenant
      mockDeviceCodeCredential.prototype.authenticate = jest.fn().mockResolvedValue({
        deviceCodeInfo: {
          userCode: 'TARGET456',
          deviceCode: 'target-device-code',
          verificationUri: 'https://microsoft.com/devicelogin',
          expiresOn: new Date(Date.now() + 900000),
          interval: 5,
          message: 'Enter code TARGET456',
        },
      });

      const targetStartResponse = await request(app)
        .post('/api/auth/device-code/start')
        .send({
          tenantType: 'target',
          tenantId: targetTenantId,
        })
        .expect(200);

      expect(targetStartResponse.body.userCode).toBe('TARGET456');

      mockDeviceCodeCredential.prototype.getToken = jest.fn().mockResolvedValue({
        token: 'target-access-token',
        expiresOnTimestamp: Date.now() + 3600000,
      });

      await request(app)
        .get('/api/auth/device-code/status')
        .query({
          tenantType: 'target',
          tenantId: targetTenantId,
        })
        .expect(200);

      // Verify both tokens stored independently
      const sourceToken = await tokenStorage.getToken('source');
      const targetToken = await tokenStorage.getToken('target');

      expect(sourceToken).not.toBeNull();
      expect(targetToken).not.toBeNull();
      expect(sourceToken!.accessToken).toBe('source-access-token');
      expect(targetToken!.accessToken).toBe('target-access-token');

      // Verify both tokens retrievable via API
      const sourceTokenResponse = await request(app)
        .get('/api/auth/token')
        .query({ tenantType: 'source' })
        .expect(200);

      const targetTokenResponse = await request(app)
        .get('/api/auth/token')
        .query({ tenantType: 'target' })
        .expect(200);

      expect(sourceTokenResponse.body.accessToken).toBe('source-access-token');
      expect(targetTokenResponse.body.accessToken).toBe('target-access-token');
    });
  });

  describe('Token Encryption and Storage Integration', () => {
    it('should encrypt token before storage and decrypt on retrieval', async () => {
      const testToken = {
        accessToken: 'sensitive-token-data',
        refreshToken: 'sensitive-refresh-token',
        expiresAt: Date.now() + 3600000,
        tenantId: sourceTenantId,
      };

      // Store token
      await tokenStorage.storeToken('source', testToken);

      // Retrieve token
      const retrievedToken = await tokenStorage.getToken('source');

      // Should match original
      expect(retrievedToken).toEqual(testToken);

      // Verify token was actually encrypted in storage
      // (by checking that raw file content doesn't contain plaintext token)
      const fs = require('fs/promises');
      const filePath = tokenStorage['_getFilePath']('source');
      const rawContent = await fs.readFile(filePath, 'utf-8');

      expect(rawContent).not.toContain('sensitive-token-data');
      expect(rawContent).not.toContain('sensitive-refresh-token');
    });
  });

  describe('Sign Out Integration', () => {
    it('should clear token from storage and API on sign out', async () => {
      // First, authenticate
      mockDeviceCodeCredential.prototype.authenticate = jest.fn().mockResolvedValue({
        deviceCodeInfo: {
          userCode: 'SIGNOUT123',
          deviceCode: 'device-code',
          verificationUri: 'https://microsoft.com/devicelogin',
          expiresOn: new Date(Date.now() + 900000),
          interval: 5,
          message: 'Enter code SIGNOUT123',
        },
      });

      await request(app)
        .post('/api/auth/device-code/start')
        .send({
          tenantType: 'source',
          tenantId: sourceTenantId,
        })
        .expect(200);

      mockDeviceCodeCredential.prototype.getToken = jest.fn().mockResolvedValue({
        token: 'token-to-be-removed',
        expiresOnTimestamp: Date.now() + 3600000,
      });

      await request(app)
        .get('/api/auth/device-code/status')
        .query({
          tenantType: 'source',
          tenantId: sourceTenantId,
        })
        .expect(200);

      // Verify token exists
      let token = await tokenStorage.getToken('source');
      expect(token).not.toBeNull();

      // Sign out
      await request(app)
        .post('/api/auth/signout')
        .send({ tenantType: 'source' })
        .expect(200);

      // Verify token removed from storage
      token = await tokenStorage.getToken('source');
      expect(token).toBeNull();

      // Verify token not retrievable via API
      await request(app)
        .get('/api/auth/token')
        .query({ tenantType: 'source' })
        .expect(401);
    });
  });

  describe('Token Refresh Integration', () => {
    it('should refresh expiring token automatically', async () => {
      // Store token that will expire soon
      const expiringToken = {
        accessToken: 'old-expiring-token',
        refreshToken: 'refresh-token',
        expiresAt: Date.now() + 240000, // 4 minutes (should trigger refresh)
        tenantId: sourceTenantId,
      };

      await tokenStorage.storeToken('source', expiringToken);

      // Mock token refresh
      mockDeviceCodeCredential.prototype.getToken = jest.fn().mockResolvedValue({
        token: 'refreshed-access-token',
        expiresOnTimestamp: Date.now() + 3600000,
      });

      // Trigger refresh via service
      const result = await authService.refreshTokenIfNeeded('source');

      expect(result.refreshed).toBe(true);
      expect(result.accessToken).toBe('refreshed-access-token');

      // Verify new token stored
      const updatedToken = await tokenStorage.getToken('source');
      expect(updatedToken!.accessToken).toBe('refreshed-access-token');
    });
  });

  describe('Error Handling Integration', () => {
    it('should handle authentication timeout gracefully', async () => {
      mockDeviceCodeCredential.prototype.authenticate = jest.fn().mockResolvedValue({
        deviceCodeInfo: {
          userCode: 'TIMEOUT123',
          deviceCode: 'device-code',
          verificationUri: 'https://microsoft.com/devicelogin',
          expiresOn: new Date(Date.now() + 900000),
          interval: 5,
          message: 'Enter code TIMEOUT123',
        },
      });

      await request(app)
        .post('/api/auth/device-code/start')
        .send({
          tenantType: 'source',
          tenantId: sourceTenantId,
        })
        .expect(200);

      // Simulate timeout
      mockDeviceCodeCredential.prototype.getToken = jest.fn().mockRejectedValue({
        name: 'AuthenticationError',
        message: 'Device code has expired',
      });

      const timeoutResponse = await request(app)
        .get('/api/auth/device-code/status')
        .query({
          tenantType: 'source',
          tenantId: sourceTenantId,
        })
        .expect(408);

      expect(timeoutResponse.body.status).toBe('expired');

      // Verify no token was stored
      const token = await tokenStorage.getToken('source');
      expect(token).toBeNull();
    });

    it('should handle corrupted token file gracefully', async () => {
      // Manually write corrupted token file
      const fs = require('fs/promises');
      const filePath = tokenStorage['_getFilePath']('source');

      await fs.mkdir(require('path').dirname(filePath), { recursive: true });
      await fs.writeFile(filePath, 'corrupted-not-valid-encryption-data');

      // Attempt to retrieve token
      const token = await tokenStorage.getToken('source');

      // Should return null or throw clear error (not crash)
      expect(token).toBeNull();
    });
  });

  describe('Security - Tenant Validation Integration', () => {
    it('should prevent cross-tenant token usage (SECURITY CRITICAL)', async () => {
      // Store token for source tenant
      const sourceToken = {
        accessToken: 'source-token',
        refreshToken: 'source-refresh',
        expiresAt: Date.now() + 3600000,
        tenantId: sourceTenantId,
      };

      await tokenStorage.storeToken('source', sourceToken);

      // Attempt to use source token for target tenant (should fail)
      const result = await authService.getTokenForTenant('target', targetTenantId);

      expect(result).toBeNull(); // Should not return wrong tenant token

      // Verify no cross-contamination
      const targetToken = await tokenStorage.getToken('target');
      expect(targetToken).toBeNull();
    });
  });

  describe('Concurrent Operations Integration', () => {
    it('should handle concurrent authentication attempts', async () => {
      mockDeviceCodeCredential.prototype.authenticate = jest.fn().mockResolvedValue({
        deviceCodeInfo: {
          userCode: 'CONCURRENT123',
          deviceCode: 'device-code',
          verificationUri: 'https://microsoft.com/devicelogin',
          expiresOn: new Date(Date.now() + 900000),
          interval: 5,
          message: 'Enter code CONCURRENT123',
        },
      });

      // Start multiple authentication flows concurrently
      const requests = [
        request(app)
          .post('/api/auth/device-code/start')
          .send({ tenantType: 'source', tenantId: sourceTenantId }),
        request(app)
          .post('/api/auth/device-code/start')
          .send({ tenantType: 'target', tenantId: targetTenantId }),
      ];

      const responses = await Promise.all(requests);

      // Both should succeed
      expect(responses[0].status).toBe(200);
      expect(responses[1].status).toBe(200);

      // Both should have valid device codes
      expect(responses[0].body.userCode).toBeDefined();
      expect(responses[1].body.userCode).toBeDefined();
    });
  });
});
