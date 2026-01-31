/**
 * TDD Tests for TokenStorageService
 *
 * Testing Strategy:
 * - Unit tests (60% of test suite)
 * - Mock file system operations
 * - Test encryption/decryption, storage/retrieval, error handling
 *
 * These tests will FAIL initially (TDD approach) until implementation is complete.
 */

import { TokenStorageService } from '../token-storage.service';
import * as fs from 'fs/promises';
import * as crypto from 'crypto';

// Mock file system
jest.mock('fs/promises');
const mockFs = fs as jest.Mocked<typeof fs>;

describe('TokenStorageService - Unit Tests (60% coverage)', () => {
  let service: TokenStorageService;
  const mockEncryptionKey = 'test-encryption-key-32-bytes-long!';

  beforeEach(() => {
    service = new TokenStorageService(mockEncryptionKey);
    jest.clearAllMocks();
  });

  describe('Token Encryption', () => {
    it('should encrypt tokens using AES-256-GCM', async () => {
      const token = {
        accessToken: 'mock-access-token',
        refreshToken: 'mock-refresh-token',
        expiresAt: Date.now() + 3600000,
        tenantId: 'source-tenant-id',
      };

      const encrypted = await service.encryptToken(token);

      // Encrypted data should be different from original
      expect(encrypted).not.toContain('mock-access-token');
      expect(encrypted).not.toContain('mock-refresh-token');

      // Should include IV and auth tag
      expect(encrypted).toMatch(/^[a-f0-9]+$/); // Hex string
      expect(encrypted.length).toBeGreaterThan(100);
    });

    it('should decrypt tokens correctly', async () => {
      const token = {
        accessToken: 'mock-access-token',
        refreshToken: 'mock-refresh-token',
        expiresAt: Date.now() + 3600000,
        tenantId: 'source-tenant-id',
      };

      const encrypted = await service.encryptToken(token);
      const decrypted = await service.decryptToken(encrypted);

      expect(decrypted).toEqual(token);
    });

    it('should throw error on decryption with wrong key', async () => {
      const token = {
        accessToken: 'mock-access-token',
        refreshToken: 'mock-refresh-token',
        expiresAt: Date.now() + 3600000,
        tenantId: 'source-tenant-id',
      };

      const encrypted = await service.encryptToken(token);

      // Create new service with different key
      const wrongKeyService = new TokenStorageService('wrong-key-32-bytes-long-wrong!');

      await expect(wrongKeyService.decryptToken(encrypted)).rejects.toThrow();
    });

    it('should throw error on decryption of corrupted data', async () => {
      const corruptedData = 'corrupted-hex-string-not-valid';

      await expect(service.decryptToken(corruptedData)).rejects.toThrow('Failed to decrypt token');
    });
  });

  describe('Token Storage', () => {
    it('should store source tenant token to file', async () => {
      const token = {
        accessToken: 'source-access-token',
        refreshToken: 'source-refresh-token',
        expiresAt: Date.now() + 3600000,
        tenantId: 'source-tenant-id',
      };

      mockFs.writeFile.mockResolvedValue(undefined);

      await service.storeToken('source', token);

      expect(mockFs.writeFile).toHaveBeenCalledTimes(1);
      const [path, data] = mockFs.writeFile.mock.calls[0];

      expect(path).toContain('source-tenant-token.enc');
      expect(typeof data).toBe('string');
      expect(data).not.toContain('source-access-token'); // Should be encrypted
    });

    it('should store target tenant token to file', async () => {
      const token = {
        accessToken: 'target-access-token',
        refreshToken: 'target-refresh-token',
        expiresAt: Date.now() + 3600000,
        tenantId: 'target-tenant-id',
      };

      mockFs.writeFile.mockResolvedValue(undefined);

      await service.storeToken('target', token);

      expect(mockFs.writeFile).toHaveBeenCalledTimes(1);
      const [path] = mockFs.writeFile.mock.calls[0];

      expect(path).toContain('target-tenant-token.enc');
    });

    it('should throw error on file write failure', async () => {
      const token = {
        accessToken: 'test-token',
        refreshToken: 'test-refresh',
        expiresAt: Date.now() + 3600000,
        tenantId: 'test-tenant',
      };

      mockFs.writeFile.mockRejectedValue(new Error('Disk full'));

      await expect(service.storeToken('source', token)).rejects.toThrow('Failed to store token');
    });
  });

  describe('Token Retrieval', () => {
    it('should retrieve and decrypt source tenant token', async () => {
      const token = {
        accessToken: 'source-access-token',
        refreshToken: 'source-refresh-token',
        expiresAt: Date.now() + 3600000,
        tenantId: 'source-tenant-id',
      };

      const encrypted = await service.encryptToken(token);
      mockFs.readFile.mockResolvedValue(encrypted);

      const retrieved = await service.getToken('source');

      expect(retrieved).toEqual(token);
      expect(mockFs.readFile).toHaveBeenCalledWith(expect.stringContaining('source-tenant-token.enc'), 'utf-8');
    });

    it('should retrieve and decrypt target tenant token', async () => {
      const token = {
        accessToken: 'target-access-token',
        refreshToken: 'target-refresh-token',
        expiresAt: Date.now() + 3600000,
        tenantId: 'target-tenant-id',
      };

      const encrypted = await service.encryptToken(token);
      mockFs.readFile.mockResolvedValue(encrypted);

      const retrieved = await service.getToken('target');

      expect(retrieved).toEqual(token);
      expect(mockFs.readFile).toHaveBeenCalledWith(expect.stringContaining('target-tenant-token.enc'), 'utf-8');
    });

    it('should return null if token file does not exist', async () => {
      mockFs.readFile.mockRejectedValue({ code: 'ENOENT' });

      const retrieved = await service.getToken('source');

      expect(retrieved).toBeNull();
    });

    it('should throw error on corrupted token file', async () => {
      mockFs.readFile.mockResolvedValue('corrupted-data-not-valid-encryption');

      await expect(service.getToken('source')).rejects.toThrow('Failed to retrieve token');
    });

    it('should handle permission errors gracefully', async () => {
      mockFs.readFile.mockRejectedValue({ code: 'EACCES' });

      await expect(service.getToken('source')).rejects.toThrow('Failed to retrieve token');
    });
  });

  describe('Token Validation', () => {
    it('should validate tenant ID matches token tenant ID', async () => {
      const token = {
        accessToken: 'test-token',
        refreshToken: 'test-refresh',
        expiresAt: Date.now() + 3600000,
        tenantId: 'expected-tenant-id',
      };

      const isValid = await service.validateTenantId(token, 'expected-tenant-id');

      expect(isValid).toBe(true);
    });

    it('should reject token with wrong tenant ID (SECURITY CRITICAL)', async () => {
      const token = {
        accessToken: 'test-token',
        refreshToken: 'test-refresh',
        expiresAt: Date.now() + 3600000,
        tenantId: 'wrong-tenant-id',
      };

      const isValid = await service.validateTenantId(token, 'expected-tenant-id');

      expect(isValid).toBe(false);
    });

    it('should check if token is expired', () => {
      const expiredToken = {
        accessToken: 'test-token',
        refreshToken: 'test-refresh',
        expiresAt: Date.now() - 1000, // Expired 1 second ago
        tenantId: 'test-tenant',
      };

      const isExpired = service.isTokenExpired(expiredToken);

      expect(isExpired).toBe(true);
    });

    it('should check if token is not expired', () => {
      const validToken = {
        accessToken: 'test-token',
        refreshToken: 'test-refresh',
        expiresAt: Date.now() + 3600000, // Expires in 1 hour
        tenantId: 'test-tenant',
      };

      const isExpired = service.isTokenExpired(validToken);

      expect(isExpired).toBe(false);
    });

    it('should check if token expires within 5 minutes', () => {
      const soonToExpireToken = {
        accessToken: 'test-token',
        refreshToken: 'test-refresh',
        expiresAt: Date.now() + 240000, // Expires in 4 minutes
        tenantId: 'test-tenant',
      };

      const needsRefresh = service.needsRefresh(soonToExpireToken);

      expect(needsRefresh).toBe(true);
    });
  });

  describe('Token Clearing', () => {
    it('should clear source tenant token', async () => {
      mockFs.unlink.mockResolvedValue(undefined);

      await service.clearToken('source');

      expect(mockFs.unlink).toHaveBeenCalledWith(expect.stringContaining('source-tenant-token.enc'));
    });

    it('should clear target tenant token', async () => {
      mockFs.unlink.mockResolvedValue(undefined);

      await service.clearToken('target');

      expect(mockFs.unlink).toHaveBeenCalledWith(expect.stringContaining('target-tenant-token.enc'));
    });

    it('should clear all tokens', async () => {
      mockFs.unlink.mockResolvedValue(undefined);

      await service.clearAllTokens();

      expect(mockFs.unlink).toHaveBeenCalledTimes(2);
      expect(mockFs.unlink).toHaveBeenCalledWith(expect.stringContaining('source-tenant-token.enc'));
      expect(mockFs.unlink).toHaveBeenCalledWith(expect.stringContaining('target-tenant-token.enc'));
    });

    it('should not throw error if token file does not exist during clear', async () => {
      mockFs.unlink.mockRejectedValue({ code: 'ENOENT' });

      // Should not throw
      await expect(service.clearToken('source')).resolves.not.toThrow();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty token gracefully', async () => {
      const emptyToken = {
        accessToken: '',
        refreshToken: '',
        expiresAt: Date.now(),
        tenantId: '',
      };

      await expect(service.encryptToken(emptyToken)).resolves.toBeDefined();
    });

    it('should handle very long tokens', async () => {
      const longToken = {
        accessToken: 'a'.repeat(10000),
        refreshToken: 'b'.repeat(10000),
        expiresAt: Date.now() + 3600000,
        tenantId: 'test-tenant',
      };

      const encrypted = await service.encryptToken(longToken);
      const decrypted = await service.decryptToken(encrypted);

      expect(decrypted).toEqual(longToken);
    });

    it('should handle special characters in tenant ID', async () => {
      const token = {
        accessToken: 'test-token',
        refreshToken: 'test-refresh',
        expiresAt: Date.now() + 3600000,
        tenantId: 'tenant-with-special-chars-@#$%',
      };

      mockFs.writeFile.mockResolvedValue(undefined);

      await expect(service.storeToken('source', token)).resolves.not.toThrow();
    });
  });
});
