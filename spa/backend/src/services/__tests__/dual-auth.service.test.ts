/**
 * TDD Tests for DualAuthService
 *
 * Testing Strategy:
 * - Unit tests (60% of test suite)
 * - Mock Azure MSAL and TokenStorageService
 * - Test device code flow, token refresh, tenant validation
 *
 * These tests will FAIL initially (TDD approach) until implementation is complete.
 */

import { DualAuthService } from '../dual-auth.service';
import { TokenStorageService } from '../token-storage.service';
import { DeviceCodeCredential } from '@azure/identity';

// Mock dependencies
jest.mock('../token-storage.service');
jest.mock('@azure/identity');

const mockTokenStorage = TokenStorageService as jest.MockedClass<typeof TokenStorageService>;
const mockDeviceCodeCredential = DeviceCodeCredential as jest.MockedClass<typeof DeviceCodeCredential>;

describe('DualAuthService - Unit Tests (60% coverage)', () => {
  let service: DualAuthService;
  let mockStorage: jest.Mocked<TokenStorageService>;

  const sourceTenantId = 'source-tenant-12345';
  const targetTenantId = 'target-tenant-67890';
  const clientId = 'test-client-id';

  beforeEach(() => {
    mockStorage = new mockTokenStorage() as jest.Mocked<TokenStorageService>;
    service = new DualAuthService(mockStorage, clientId);
    jest.clearAllMocks();
  });

  describe('Device Code Flow - Start', () => {
    it('should start device code flow for source tenant', async () => {
      const mockDeviceCodeInfo = {
        userCode: 'ABCD1234',
        deviceCode: 'device-code-12345',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresOn: new Date(Date.now() + 900000), // 15 minutes
        interval: 5,
        message: 'To sign in, use a web browser to open the page https://microsoft.com/devicelogin and enter the code ABCD1234 to authenticate.',
      };

      // Mock the DeviceCodeCredential constructor to capture callback
      let userPromptCallback: any;
      (DeviceCodeCredential as any).mockImplementation((options: any) => {
        userPromptCallback = options.userPromptCallback;
        return {
          getToken: jest.fn().mockImplementation(async () => {
            // Trigger the callback with device code info
            if (userPromptCallback) {
              userPromptCallback(mockDeviceCodeInfo);
            }
            // Return a promise that never resolves (device code flow waits for user)
            return new Promise(() => {});
          }),
        };
      });

      const result = await service.startDeviceCodeFlow('source', sourceTenantId);

      expect(result).toEqual({
        userCode: 'ABCD1234',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresIn: expect.any(Number),
        message: expect.stringContaining('ABCD1234'),
        requestId: expect.any(String),
      });

      expect(DeviceCodeCredential).toHaveBeenCalledWith({
        tenantId: sourceTenantId,
        clientId: clientId,
        userPromptCallback: expect.any(Function),
      });
    });

    it('should start device code flow for target tenant', async () => {
      const mockDeviceCodeInfo = {
        userCode: 'EFGH5678',
        deviceCode: 'device-code-67890',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresOn: new Date(Date.now() + 900000),
        interval: 5,
        message: 'To sign in, use a web browser to open the page https://microsoft.com/devicelogin and enter the code EFGH5678 to authenticate.',
      };

      // Mock the DeviceCodeCredential constructor to capture callback
      let userPromptCallback: any;
      (DeviceCodeCredential as any).mockImplementation((options: any) => {
        userPromptCallback = options.userPromptCallback;
        return {
          getToken: jest.fn().mockImplementation(async () => {
            // Trigger the callback with device code info
            if (userPromptCallback) {
              userPromptCallback(mockDeviceCodeInfo);
            }
            // Return a promise that never resolves (device code flow waits for user)
            return new Promise(() => {});
          }),
        };
      });

      const result = await service.startDeviceCodeFlow('target', targetTenantId);

      expect(result).toEqual({
        userCode: 'EFGH5678',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresIn: expect.any(Number),
        message: expect.stringContaining('EFGH5678'),
        requestId: expect.any(String),
      });

      expect(DeviceCodeCredential).toHaveBeenCalledWith({
        tenantId: targetTenantId,
        clientId: clientId,
        userPromptCallback: expect.any(Function),
      });
    });

    it('should throw error if tenant ID is invalid', async () => {
      await expect(service.startDeviceCodeFlow('source', '')).rejects.toThrow('Invalid tenant ID');
    });

    it('should throw error if tenant type is invalid', async () => {
      await expect(service.startDeviceCodeFlow('invalid' as any, sourceTenantId)).rejects.toThrow('Invalid tenant type');
    });

    it('should handle Azure AD errors gracefully', async () => {
      // Mock credential that throws error on getToken
      (DeviceCodeCredential as any).mockImplementation(() => {
        return {
          getToken: jest.fn().mockRejectedValue(
            new Error('Azure AD service unavailable')
          ),
        };
      });

      await expect(service.startDeviceCodeFlow('source', sourceTenantId)).rejects.toThrow('Failed to start device code flow');
    });
  });

  describe('Device Code Flow - Polling', () => {
    it('should poll for authentication completion (success)', async () => {
      const mockToken = {
        token: 'mock-access-token',
        expiresOnTimestamp: Date.now() + 3600000,
      };

      // Mock DeviceCodeCredential constructor
      (DeviceCodeCredential as any).mockImplementation(() => {
        return {
          getToken: jest.fn().mockResolvedValue(mockToken),
        };
      });

      mockStorage.storeToken.mockResolvedValue(undefined);
      mockStorage.validateTenantId.mockResolvedValue(true); // Validation passes

      const result = await service.pollForAuthentication('source', sourceTenantId);

      expect(result).toEqual({
        success: true,
        accessToken: 'mock-access-token',
        expiresAt: mockToken.expiresOnTimestamp,
      });

      expect(mockStorage.storeToken).toHaveBeenCalledWith('source', {
        accessToken: 'mock-access-token',
        refreshToken: 'mock-access-token', // Device code flow uses same token
        expiresAt: mockToken.expiresOnTimestamp,
        tenantId: sourceTenantId,
      });
    });

    it('should poll for authentication completion (pending)', async () => {
      // Create proper Error object
      const pendingError = new Error('User has not yet authenticated');
      pendingError.name = 'CredentialUnavailableError';

      // Mock DeviceCodeCredential to throw pending error
      (DeviceCodeCredential as any).mockImplementation(() => {
        return {
          getToken: jest.fn().mockRejectedValue(pendingError),
        };
      });

      const result = await service.pollForAuthentication('source', sourceTenantId);

      expect(result).toEqual({
        success: false,
        status: 'pending',
        message: 'User has not yet authenticated',
      });

      expect(mockStorage.storeToken).not.toHaveBeenCalled();
    });

    it('should poll for authentication completion (expired)', async () => {
      // Create proper Error object
      const expiredError = new Error('Device code has expired');
      expiredError.name = 'AuthenticationError';

      // Mock DeviceCodeCredential to throw expired error
      (DeviceCodeCredential as any).mockImplementation(() => {
        return {
          getToken: jest.fn().mockRejectedValue(expiredError),
        };
      });

      const result = await service.pollForAuthentication('source', sourceTenantId);

      expect(result).toEqual({
        success: false,
        status: 'expired',
        message: 'Device code has expired',
      });
    });

    it('should validate tenant ID before storing token (SECURITY CRITICAL)', async () => {
      const mockToken = {
        token: 'mock-access-token',
        expiresOnTimestamp: Date.now() + 3600000,
      };

      mockDeviceCodeCredential.prototype.getToken = jest.fn().mockResolvedValue(mockToken);
      mockStorage.validateTenantId.mockResolvedValue(false); // Tenant mismatch

      await expect(service.pollForAuthentication('source', sourceTenantId)).rejects.toThrow('Tenant ID validation failed');

      expect(mockStorage.storeToken).not.toHaveBeenCalled();
    });
  });

  describe('Token Refresh', () => {
    it('should refresh token if expires within 5 minutes', async () => {
      const oldToken = {
        accessToken: 'old-access-token',
        refreshToken: 'old-refresh-token',
        expiresAt: Date.now() + 240000, // 4 minutes
        tenantId: sourceTenantId,
      };

      const newToken = {
        token: 'new-access-token',
        expiresOnTimestamp: Date.now() + 3600000, // 1 hour
      };

      mockStorage.getToken.mockResolvedValue(oldToken);
      mockStorage.needsRefresh.mockReturnValue(true);

      // Mock DeviceCodeCredential instance method
      (DeviceCodeCredential as any).mockImplementation(() => {
        return {
          getToken: jest.fn().mockResolvedValue(newToken),
        };
      });

      mockStorage.storeToken.mockResolvedValue(undefined);

      const result = await service.refreshTokenIfNeeded('source');

      expect(result).toEqual({
        refreshed: true,
        accessToken: 'new-access-token',
        expiresAt: newToken.expiresOnTimestamp,
      });

      expect(mockStorage.storeToken).toHaveBeenCalledWith('source', {
        accessToken: 'new-access-token',
        refreshToken: oldToken.refreshToken,
        expiresAt: newToken.expiresOnTimestamp,
        tenantId: sourceTenantId,
      });
    });

    it('should not refresh token if still valid', async () => {
      const validToken = {
        accessToken: 'valid-access-token',
        refreshToken: 'valid-refresh-token',
        expiresAt: Date.now() + 3600000, // 1 hour
        tenantId: sourceTenantId,
      };

      mockStorage.getToken.mockResolvedValue(validToken);
      mockStorage.needsRefresh.mockReturnValue(false);

      const result = await service.refreshTokenIfNeeded('source');

      expect(result).toEqual({
        refreshed: false,
        message: 'Token still valid',
      });

      expect(mockStorage.storeToken).not.toHaveBeenCalled();
    });

    it('should return error if no token exists', async () => {
      mockStorage.getToken.mockResolvedValue(null);

      const result = await service.refreshTokenIfNeeded('source');

      expect(result).toEqual({
        refreshed: false,
        error: 'No token found',
      });
    });

    it('should handle refresh failure gracefully', async () => {
      const oldToken = {
        accessToken: 'old-access-token',
        refreshToken: 'old-refresh-token',
        expiresAt: Date.now() + 240000,
        tenantId: sourceTenantId,
      };

      mockStorage.getToken.mockResolvedValue(oldToken);
      mockStorage.needsRefresh.mockReturnValue(true);

      // Mock DeviceCodeCredential to throw error
      (DeviceCodeCredential as any).mockImplementation(() => {
        return {
          getToken: jest.fn().mockRejectedValue(new Error('Refresh token expired')),
        };
      });

      const result = await service.refreshTokenIfNeeded('source');

      expect(result).toEqual({
        refreshed: false,
        error: 'Token refresh failed',
      });
    });
  });

  describe('Auto-Refresh Timer', () => {
    it('should start auto-refresh timer for both tenants', () => {
      const mockSetInterval = jest.spyOn(global, 'setInterval');

      service.startAutoRefresh();

      expect(mockSetInterval).toHaveBeenCalledWith(expect.any(Function), 240000); // 4 minutes
    });

    it('should stop auto-refresh timer', () => {
      const mockClearInterval = jest.spyOn(global, 'clearInterval');

      service.startAutoRefresh();
      service.stopAutoRefresh();

      expect(mockClearInterval).toHaveBeenCalled();
    });

    it('should refresh both tenants during auto-refresh cycle', async () => {
      jest.useFakeTimers();

      const refreshSpy = jest.spyOn(service, 'refreshTokenIfNeeded').mockResolvedValue({
        refreshed: true,
        accessToken: 'new-token',
        expiresAt: Date.now() + 3600000,
      });

      service.startAutoRefresh();

      // Fast-forward 4 minutes
      jest.advanceTimersByTime(240000);

      await Promise.resolve(); // Allow promises to resolve

      expect(refreshSpy).toHaveBeenCalledWith('source');
      expect(refreshSpy).toHaveBeenCalledWith('target');

      jest.useRealTimers();
    });
  });

  describe('Sign Out', () => {
    it('should sign out source tenant', async () => {
      mockStorage.clearToken.mockResolvedValue(undefined);

      await service.signOut('source');

      expect(mockStorage.clearToken).toHaveBeenCalledWith('source');
    });

    it('should sign out target tenant', async () => {
      mockStorage.clearToken.mockResolvedValue(undefined);

      await service.signOut('target');

      expect(mockStorage.clearToken).toHaveBeenCalledWith('target');
    });

    it('should sign out all tenants', async () => {
      mockStorage.clearAllTokens.mockResolvedValue(undefined);

      // Spy on stopAutoRefresh method
      const stopAutoRefreshSpy = jest.spyOn(service, 'stopAutoRefresh');

      await service.signOutAll();

      expect(mockStorage.clearAllTokens).toHaveBeenCalled();
      expect(stopAutoRefreshSpy).toHaveBeenCalled();

      // Clean up spy
      stopAutoRefreshSpy.mockRestore();
    });
  });

  describe('Get Authentication Status', () => {
    it('should return authenticated status for source tenant', async () => {
      const validToken = {
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
        expiresAt: Date.now() + 3600000,
        tenantId: sourceTenantId,
      };

      mockStorage.getToken.mockResolvedValue(validToken);
      mockStorage.isTokenExpired.mockReturnValue(false);

      const status = await service.getAuthStatus('source');

      expect(status).toEqual({
        authenticated: true,
        tenantId: sourceTenantId,
        expiresAt: validToken.expiresAt,
      });
    });

    it('should return not authenticated if no token exists', async () => {
      mockStorage.getToken.mockResolvedValue(null);

      const status = await service.getAuthStatus('source');

      expect(status).toEqual({
        authenticated: false,
      });
    });

    it('should return not authenticated if token is expired', async () => {
      const expiredToken = {
        accessToken: 'expired-token',
        refreshToken: 'expired-refresh',
        expiresAt: Date.now() - 1000,
        tenantId: sourceTenantId,
      };

      mockStorage.getToken.mockResolvedValue(expiredToken);
      mockStorage.isTokenExpired.mockReturnValue(true);

      const status = await service.getAuthStatus('source');

      expect(status).toEqual({
        authenticated: false,
        error: 'Token expired',
      });
    });
  });

  describe('Security - Tenant Validation', () => {
    it('should validate tenant ID matches expected tenant (CRITICAL)', async () => {
      const token = {
        accessToken: 'test-token',
        refreshToken: 'test-refresh',
        expiresAt: Date.now() + 3600000,
        tenantId: 'correct-tenant-id',
      };

      mockStorage.validateTenantId.mockResolvedValue(true);

      const isValid = await service.validateTenantId(token, 'correct-tenant-id');

      expect(isValid).toBe(true);
    });

    it('should reject token with wrong tenant ID (CRITICAL)', async () => {
      const token = {
        accessToken: 'test-token',
        refreshToken: 'test-refresh',
        expiresAt: Date.now() + 3600000,
        tenantId: 'wrong-tenant-id',
      };

      mockStorage.validateTenantId.mockResolvedValue(false);

      const isValid = await service.validateTenantId(token, 'correct-tenant-id');

      expect(isValid).toBe(false);
    });

    it('should prevent cross-tenant token usage (SECURITY CRITICAL)', async () => {
      const sourceToken = {
        accessToken: 'source-token',
        refreshToken: 'source-refresh',
        expiresAt: Date.now() + 3600000,
        tenantId: sourceTenantId,
      };

      mockStorage.getToken.mockResolvedValue(sourceToken);
      mockStorage.validateTenantId.mockImplementation((token, expectedTenant) => {
        return Promise.resolve(token.tenantId === expectedTenant);
      });

      // Try to use source token for target tenant
      await expect(service.getTokenForTenant('target', targetTenantId)).rejects.toThrow('Tenant ID mismatch');
    });
  });

  describe('Edge Cases', () => {
    it('should handle concurrent token refresh requests', async () => {
      const oldToken = {
        accessToken: 'old-token',
        refreshToken: 'old-refresh',
        expiresAt: Date.now() + 240000,
        tenantId: sourceTenantId,
      };

      mockStorage.getToken.mockResolvedValue(oldToken);
      mockStorage.needsRefresh.mockReturnValue(true);

      // Mock DeviceCodeCredential instance method
      (DeviceCodeCredential as any).mockImplementation(() => {
        return {
          getToken: jest.fn().mockResolvedValue({
            token: 'new-token',
            expiresOnTimestamp: Date.now() + 3600000,
          }),
        };
      });

      mockStorage.storeToken.mockResolvedValue(undefined);

      // Simulate concurrent refresh requests
      const results = await Promise.all([
        service.refreshTokenIfNeeded('source'),
        service.refreshTokenIfNeeded('source'),
        service.refreshTokenIfNeeded('source'),
      ]);

      // Should only refresh once (first request succeeds, others skip due to refreshInProgress flag)
      expect(mockStorage.storeToken).toHaveBeenCalledTimes(1);
    });

    it('should handle network timeout during authentication', async () => {
      // Create proper Error object with name property
      const networkError = new Error('Request timeout');
      networkError.name = 'NetworkError';

      mockDeviceCodeCredential.prototype.getToken = jest.fn().mockRejectedValue(networkError);

      await expect(service.pollForAuthentication('source', sourceTenantId)).rejects.toThrow('Network error during authentication');
    });
  });
});
