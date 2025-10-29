/**
 * Secure credential management module
 * Handles environment variables and secure storage of sensitive data
 */

import { createCipheriv, createDecipheriv, randomBytes, scryptSync } from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { logger } from '../logger';

// Configuration
const CONFIG = {
  ENCRYPTION_ALGORITHM: 'aes-256-gcm',
  SALT_LENGTH: 32,
  KEY_LENGTH: 32,
  IV_LENGTH: 16,
  AUTH_TAG_LENGTH: 16
};

interface EncryptedCredential {
  encrypted: string;
  iv: string;
  authTag: string;
  salt: string;
}

interface Neo4jCredentials {
  uri: string;
  username: string;
  password: string;
}

export class CredentialManager {
  private static masterKey: Buffer | null = null;

  /**
   * Initialize the credential manager with a master key
   * In production, this should come from a secure key management service
   */
  static initialize() {
    // Try to get master key from environment
    const masterKeyEnv = process.env.CREDENTIAL_MASTER_KEY;
    
    if (masterKeyEnv) {
      this.masterKey = Buffer.from(masterKeyEnv, 'hex');
      logger.info('Credential manager initialized with environment key');
    } else {
      // Generate a key for development (NOT for production)
      const keyPath = path.join(process.cwd(), '.credential-key');
      
      if (fs.existsSync(keyPath)) {
        this.masterKey = fs.readFileSync(keyPath);
        logger.info('Credential manager initialized with stored key');
      } else {
        this.masterKey = randomBytes(CONFIG.KEY_LENGTH);
        fs.writeFileSync(keyPath, this.masterKey);
        logger.warn('Generated new credential key (development only)');
      }
    }
  }

  /**
   * Get Neo4j credentials from environment or secure storage
   */
  static getNeo4jCredentials(): Neo4jCredentials {
    // First, try environment variables
    const envUri = process.env.NEO4J_URI;
    const envUser = process.env.NEO4J_USER || process.env.NEO4J_USERNAME;
    const envPassword = process.env.NEO4J_PASSWORD;

    if (envUri && envUser && envPassword) {
      logger.info('Using Neo4j credentials from environment variables');
      return {
        uri: envUri,
        username: envUser,
        password: envPassword
      };
    }

    // Try to load from encrypted file
    const credPath = path.join(process.cwd(), '.neo4j-credentials.enc');
    
    if (fs.existsSync(credPath)) {
      try {
        const encryptedData = JSON.parse(fs.readFileSync(credPath, 'utf8'));
        const decrypted = this.decryptCredentials(encryptedData);
        logger.info('Using Neo4j credentials from encrypted storage');
        return decrypted;
      } catch (error) {
        logger.error('Failed to decrypt Neo4j credentials', error);
      }
    }

    // Fallback to environment variables (development only)
    if (process.env.NODE_ENV !== 'production') {
      const password = process.env.NEO4J_PASSWORD;
      if (password) {
        logger.warn('Using Neo4j credentials from environment (development only)');
        return {
          uri: process.env.NEO4J_URI || 'bolt://localhost:7687',
          username: process.env.NEO4J_USER || 'neo4j',
          password: password
        };
      }
    }

    throw new Error('Neo4j credentials not configured. Set NEO4J_PASSWORD environment variable.');
  }

  /**
   * Save Neo4j credentials securely
   */
  static saveNeo4jCredentials(credentials: Neo4jCredentials): void {
    if (!this.masterKey) {
      this.initialize();
    }

    const encrypted = this.encryptCredentials(credentials);
    const credPath = path.join(process.cwd(), '.neo4j-credentials.enc');
    
    fs.writeFileSync(credPath, JSON.stringify(encrypted, null, 2));
    logger.info('Neo4j credentials saved to encrypted storage');
  }

  /**
   * Encrypt credentials
   */
  private static encryptCredentials(credentials: Neo4jCredentials): EncryptedCredential {
    if (!this.masterKey) {
      throw new Error('Credential manager not initialized');
    }

    const salt = randomBytes(CONFIG.SALT_LENGTH);
    const key = scryptSync(this.masterKey, salt, CONFIG.KEY_LENGTH);
    const iv = randomBytes(CONFIG.IV_LENGTH);
    
    const cipher = createCipheriv(CONFIG.ENCRYPTION_ALGORITHM, key, iv) as any;
    
    const plaintext = JSON.stringify(credentials);
    const encrypted = Buffer.concat([
      cipher.update(plaintext, 'utf8'),
      cipher.final()
    ]);
    
    const authTag = cipher.getAuthTag();

    return {
      encrypted: encrypted.toString('base64'),
      iv: iv.toString('base64'),
      authTag: authTag.toString('base64'),
      salt: salt.toString('base64')
    };
  }

  /**
   * Decrypt credentials
   */
  private static decryptCredentials(encryptedData: EncryptedCredential): Neo4jCredentials {
    if (!this.masterKey) {
      throw new Error('Credential manager not initialized');
    }

    const salt = Buffer.from(encryptedData.salt, 'base64');
    const key = scryptSync(this.masterKey, salt, CONFIG.KEY_LENGTH);
    const iv = Buffer.from(encryptedData.iv, 'base64');
    const authTag = Buffer.from(encryptedData.authTag, 'base64');
    
    const decipher = createDecipheriv(CONFIG.ENCRYPTION_ALGORITHM, key, iv) as any;
    decipher.setAuthTag(authTag);
    
    const decrypted = Buffer.concat([
      decipher.update(Buffer.from(encryptedData.encrypted, 'base64')),
      decipher.final()
    ]);

    return JSON.parse(decrypted.toString('utf8'));
  }

  /**
   * Validate credential format
   */
  static validateCredentials(credentials: Neo4jCredentials): boolean {
    if (!credentials.uri || !credentials.username || !credentials.password) {
      return false;
    }

    // Validate URI format
    const uriPattern = /^(bolt|neo4j|neo4j\+s|neo4j\+ssc):\/\/[a-zA-Z0-9.-]+(:[0-9]+)?$/;
    if (!uriPattern.test(credentials.uri)) {
      logger.error('Invalid Neo4j URI format');
      return false;
    }

    // Validate username (alphanumeric and underscore only)
    const usernamePattern = /^[a-zA-Z0-9_]+$/;
    if (!usernamePattern.test(credentials.username)) {
      logger.error('Invalid Neo4j username format');
      return false;
    }

    // Password should not be empty
    if (credentials.password.length < 1) {
      logger.error('Neo4j password cannot be empty');
      return false;
    }

    return true;
  }

  /**
   * Get Azure credentials from environment
   */
  static getAzureCredentials(): { tenantId?: string; clientId?: string; clientSecret?: string } {
    const credentials = {
      tenantId: process.env.AZURE_TENANT_ID,
      clientId: process.env.AZURE_CLIENT_ID,
      clientSecret: process.env.AZURE_CLIENT_SECRET
    };

    // Don't log the actual values, just whether they're set
    logger.info('Azure credentials status', {
      tenantIdSet: !!credentials.tenantId,
      clientIdSet: !!credentials.clientId,
      clientSecretSet: !!credentials.clientSecret
    });

    return credentials;
  }

  /**
   * Sanitize environment variables for logging
   */
  static getSanitizedEnv(): Record<string, string> {
    const env: Record<string, string> = {};
    const sensitiveKeys = [
      'PASSWORD',
      'SECRET',
      'KEY',
      'TOKEN',
      'CREDENTIAL',
      'API_KEY',
      'ACCESS_KEY'
    ];

    for (const [key, value] of Object.entries(process.env)) {
      if (!value) continue;
      
      let sanitized = value;
      
      // Check if key contains sensitive pattern
      const isSensitive = sensitiveKeys.some(pattern => key.toUpperCase().includes(pattern));
      
      if (isSensitive) {
        // Show only first 4 characters
        sanitized = value.substring(0, 4) + '****';
      }
      
      env[key] = sanitized;
    }

    return env;
  }

  /**
   * Rotate credentials
   */
  static async rotateCredentials(): Promise<void> {
    logger.info('Starting credential rotation');
    
    // Generate new master key
    const oldKey = this.masterKey;
    this.masterKey = randomBytes(CONFIG.KEY_LENGTH);
    
    // Re-encrypt stored credentials with new key
    const credPath = path.join(process.cwd(), '.neo4j-credentials.enc');
    
    if (fs.existsSync(credPath)) {
      try {
        // Decrypt with old key
        this.masterKey = oldKey;
        const encryptedData = JSON.parse(fs.readFileSync(credPath, 'utf8'));
        const credentials = this.decryptCredentials(encryptedData);
        
        // Encrypt with new key
        this.masterKey = randomBytes(CONFIG.KEY_LENGTH);
        this.saveNeo4jCredentials(credentials);
        
        // Save new key
        const keyPath = path.join(process.cwd(), '.credential-key');
        fs.writeFileSync(keyPath, this.masterKey);
        
        logger.info('Credential rotation completed successfully');
      } catch (error) {
        logger.error('Failed to rotate credentials', error);
        this.masterKey = oldKey; // Restore old key on failure
        throw error;
      }
    }
  }
}

// Initialize on module load
CredentialManager.initialize();

export default CredentialManager;