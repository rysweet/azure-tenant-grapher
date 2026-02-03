/**
 * TokenStorageService
 *
 * Provides encrypted storage for Azure authentication tokens.
 * Implements AES-256-GCM encryption with separate storage per tenant.
 *
 * Security Features:
 * - AES-256-GCM encryption for all stored tokens
 * - Separate storage files per tenant (source/target)
 * - Tenant ID validation before use (prevents cross-tenant token usage)
 * - No tokens logged or exposed in error messages
 *
 * Philosophy:
 * - Single responsibility: Token storage and encryption
 * - Standard library (crypto, fs) only
 * - Self-contained and regeneratable
 */

import * as fs from 'fs/promises';
import * as crypto from 'crypto';
import * as path from 'path';
import * as os from 'os';

// Type definitions
export interface StoredToken {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  tenantId: string;
}

export type TenantType = 'source' | 'target';

export class TokenStorageService {
  private readonly encryptionKey: Buffer;
  private readonly algorithm = 'aes-256-gcm';
  private readonly storageDir: string;

  constructor(encryptionKey: string) {
    // Convert encryption key to 32-byte buffer for AES-256
    this.encryptionKey = crypto.scryptSync(encryptionKey, 'salt', 32);

    // Store tokens in user's home directory
    this.storageDir = path.join(os.homedir(), '.azure-tenant-grapher', 'tokens');
  }

  /**
   * Encrypt token using AES-256-GCM
   * Returns hex-encoded string with IV + encrypted data + auth tag (no separators)
   */
  async encryptToken(token: StoredToken): Promise<string> {
    try {
      // Generate random IV (12 bytes for GCM)
      const iv = crypto.randomBytes(12);

      // Create cipher
      const cipher = crypto.createCipheriv(this.algorithm, this.encryptionKey, iv);

      // Encrypt token data
      const tokenJson = JSON.stringify(token);
      let encrypted = cipher.update(tokenJson, 'utf8', 'hex');
      encrypted += cipher.final('hex');

      // Get auth tag (16 bytes for GCM)
      const authTag = cipher.getAuthTag();

      // Combine IV + encrypted data + auth tag as continuous hex string
      // Format: [12 bytes IV][variable encrypted data][16 bytes auth tag]
      return iv.toString('hex') + encrypted + authTag.toString('hex');
    } catch (error) {
      throw new Error('Failed to encrypt token');
    }
  }

  /**
   * Decrypt token from hex-encoded string
   * Expected format: [24 hex chars IV][variable encrypted][32 hex chars auth tag]
   */
  async decryptToken(encryptedData: string): Promise<StoredToken> {
    try {
      // IV is first 24 hex characters (12 bytes)
      // Auth tag is last 32 hex characters (16 bytes)
      // Encrypted data is everything in between

      if (encryptedData.length < 56) { // 24 + 32 = 56 minimum
        throw new Error('Invalid encrypted data format');
      }

      const ivHex = encryptedData.slice(0, 24);
      const authTagHex = encryptedData.slice(-32);
      const encryptedHex = encryptedData.slice(24, -32);

      const iv = Buffer.from(ivHex, 'hex');
      const authTag = Buffer.from(authTagHex, 'hex');

      // Create decipher
      const decipher = crypto.createDecipheriv(this.algorithm, this.encryptionKey, iv);
      decipher.setAuthTag(authTag);

      // Decrypt
      let decrypted = decipher.update(encryptedHex, 'hex', 'utf8');
      decrypted += decipher.final('utf8');

      // Parse JSON
      return JSON.parse(decrypted) as StoredToken;
    } catch (error) {
      throw new Error('Failed to decrypt token');
    }
  }

  /**
   * Store encrypted token to file
   */
  async storeToken(tenantType: TenantType, token: StoredToken): Promise<void> {
    try {
      // Ensure storage directory exists
      await fs.mkdir(this.storageDir, { recursive: true });

      // Encrypt token
      const encrypted = await this.encryptToken(token);

      // Write to file
      const filePath = this.getTokenFilePath(tenantType);
      await fs.writeFile(filePath, encrypted, 'utf-8');
    } catch (error) {
      throw new Error('Failed to store token');
    }
  }

  /**
   * Retrieve and decrypt token from file
   */
  async getToken(tenantType: TenantType): Promise<StoredToken | null> {
    try {
      const filePath = this.getTokenFilePath(tenantType);

      // Read encrypted data
      const encrypted = await fs.readFile(filePath, 'utf-8');

      // Decrypt and return
      return await this.decryptToken(encrypted);
    } catch (error: any) {
      // Return null if file doesn't exist
      if (error.code === 'ENOENT') {
        return null;
      }

      // Throw for other errors (permission, corruption, etc.)
      throw new Error('Failed to retrieve token');
    }
  }

  /**
   * Clear token for specific tenant
   */
  async clearToken(tenantType: TenantType): Promise<void> {
    try {
      const filePath = this.getTokenFilePath(tenantType);
      await fs.unlink(filePath);
    } catch (error: any) {
      // Ignore if file doesn't exist
      if (error.code !== 'ENOENT') {
        throw error;
      }
    }
  }

  /**
   * Clear all tokens
   */
  async clearAllTokens(): Promise<void> {
    await Promise.all([
      this.clearToken('source'),
      this.clearToken('target'),
    ]);
  }

  /**
   * Validate that token's tenant ID matches expected tenant ID
   * SECURITY CRITICAL: Prevents cross-tenant token usage
   */
  async validateTenantId(token: StoredToken, expectedTenantId: string): Promise<boolean> {
    return token.tenantId === expectedTenantId;
  }

  /**
   * Check if token is expired
   */
  isTokenExpired(token: StoredToken): boolean {
    return Date.now() >= token.expiresAt;
  }

  /**
   * Check if token needs refresh (expires within 5 minutes)
   */
  needsRefresh(token: StoredToken): boolean {
    const fiveMinutes = 5 * 60 * 1000;
    return Date.now() >= (token.expiresAt - fiveMinutes);
  }

  /**
   * Get file path for tenant token
   */
  private getTokenFilePath(tenantType: TenantType): string {
    return path.join(this.storageDir, `${tenantType}-tenant-token.enc`);
  }
}
