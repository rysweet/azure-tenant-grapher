# Dual-Account Authentication Developer Guide

**Document Type**: How-To Guide + Reference
**Audience**: Developers integrating with or extending authentication system
**Last Updated**: 2026-01-29

## Overview

This guide provides developers with practical information for integrating with and extending Azure Tenant Grapher's dual-account authentication system.

## Quick Start for Developers

### Prerequisites

- Node.js 18+ and npm/yarn
- Python 3.9+ (for CLI integration)
- Azure AD app registration with Device Code Flow enabled

### Setup Development Environment

1. **Clone repository**:
   ```bash
   git clone https://github.com/org/azure-tenant-grapher.git
   cd azure-tenant-grapher
   ```

2. **Install dependencies**:
   ```bash
   # Frontend
   cd spa
   npm install

   # Backend
   cd ../backend
   npm install
   ```

3. **Configure Azure AD app**:
   ```bash
   # Copy config template
   cp config/auth.example.json config/auth.json

   # Edit config with your app registration details
   nano config/auth.json
   ```

4. **Run in development mode**:
   ```bash
   # Start backend
   npm run dev:backend

   # Start frontend (separate terminal)
   npm run dev:frontend
   ```

---

## Integration Patterns

### Using AuthContext in React Components

**Basic Usage**:

```typescript
import { useAuth } from '../context/AuthContext';

function MyComponent() {
  const { sourceAuth, gameboardAuth, signIn, signOut, getToken } = useAuth();

  // Check authentication status
  if (sourceAuth.status === 'authenticated') {
    console.log(`Authenticated as ${sourceAuth.user}`);
  }

  // Sign in
  async function handleSignIn() {
    try {
      await signIn('source');
      console.log('Sign-in initiated');
    } catch (error) {
      console.error('Sign-in failed:', error);
    }
  }

  // Sign out
  async function handleSignOut() {
    await signOut('source');
  }

  return (
    <div>
      {sourceAuth.status === 'authenticated' ? (
        <>
          <p>Signed in as {sourceAuth.user}</p>
          <button onClick={handleSignOut}>Sign Out</button>
        </>
      ) : (
        <button onClick={handleSignIn}>Sign In</button>
      )}
    </div>
  );
}
```

**Feature Gating Pattern**:

```typescript
import { useAuth } from '../context/AuthContext';
import { Link } from 'react-router-dom';

function ProtectedFeature({ requiredTenant }: { requiredTenant: 'source' | 'gameboard' }) {
  const { sourceAuth, gameboardAuth } = useAuth();

  const auth = requiredTenant === 'source' ? sourceAuth : gameboardAuth;

  if (auth.status !== 'authenticated') {
    return (
      <div className="auth-required">
        <h3>Authentication Required</h3>
        <p>Please authenticate to {requiredTenant} tenant to use this feature.</p>
        <Link to="/auth">Go to Auth Tab</Link>
      </div>
    );
  }

  // Feature content
  return <div>Protected feature content...</div>;
}

// Usage
function ScanTab() {
  return (
    <ProtectedFeature requiredTenant="source">
      <ScanControls />
    </ProtectedFeature>
  );
}
```

**Token Retrieval for API Calls**:

```typescript
import { useAuth } from '../context/AuthContext';

function AzureAPIComponent() {
  const { getToken } = useAuth();

  async function callAzureAPI() {
    try {
      // Get token
      const token = await getToken('source');

      if (!token) {
        throw new Error('Not authenticated');
      }

      // Call Azure API
      const response = await fetch(
        'https://management.azure.com/subscriptions?api-version=2020-01-01',
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('API call failed:', error);
      throw error;
    }
  }

  return <button onClick={callAzureAPI}>List Subscriptions</button>;
}
```

---

### Backend API Integration

#### Creating New Auth Endpoints

**Example: Get User Info**:

```typescript
import { Router } from 'express';
import { AuthManager } from '../services/AuthManager';
import { csrfProtection } from '../middleware/csrf';

const router = Router();
const authManager = new AuthManager();

/**
 * GET /api/auth/userinfo
 * Returns user information for authenticated tenant
 */
router.get('/api/auth/userinfo', async (req, res) => {
  try {
    const { tenantType } = req.query;

    // Validate tenant type
    if (!['source', 'gameboard'].includes(tenantType as string)) {
      return res.status(400).json({
        error: 'Invalid tenant type',
        message: 'tenantType must be "source" or "gameboard"'
      });
    }

    // Get user info
    const userInfo = await authManager.getUserInfo(tenantType as 'source' | 'gameboard');

    if (!userInfo) {
      return res.status(401).json({
        error: 'Not authenticated',
        message: `Not authenticated to ${tenantType} tenant`
      });
    }

    res.json({
      user: userInfo.user,
      tenantId: userInfo.tenantId,
      tenantName: userInfo.tenantName,
      expiresAt: userInfo.expiresAt
    });
  } catch (error) {
    console.error('Failed to get user info:', error);
    res.status(500).json({
      error: 'Failed to get user info',
      message: error.message
    });
  }
});

export default router;
```

#### Implementing Custom Token Validation

**Example: Validate Token for Specific Resource**:

```typescript
import { AuthManager } from '../services/AuthManager';

class CustomTokenValidator {
  constructor(private authManager: AuthManager) {}

  /**
   * Validate token has required permissions for resource
   */
  async validateTokenForResource(
    tenantType: 'source' | 'gameboard',
    resourceId: string,
    requiredPermissions: string[]
  ): Promise<boolean> {
    // Get token
    const token = await this.authManager.getAccessToken(tenantType);

    if (!token) {
      throw new Error('Not authenticated');
    }

    // Decode token
    const decoded = jwt.decode(token) as any;

    // Validate expiration
    if (decoded.exp < Date.now() / 1000) {
      throw new Error('Token expired');
    }

    // Validate tenant
    const expectedTenantId = await this.authManager.getTenantId(tenantType);
    if (decoded.tid !== expectedTenantId) {
      throw new Error('Token tenant mismatch');
    }

    // Validate scope
    const tokenScopes = decoded.scp?.split(' ') || [];

    for (const requiredPermission of requiredPermissions) {
      if (!tokenScopes.includes(requiredPermission)) {
        throw new Error(`Missing required permission: ${requiredPermission}`);
      }
    }

    // Optionally: Call Azure API to verify resource access
    try {
      await this.verifyResourceAccess(token, resourceId);
    } catch (error) {
      throw new Error('Token does not have access to resource');
    }

    return true;
  }

  private async verifyResourceAccess(token: string, resourceId: string): Promise<void> {
    const response = await fetch(
      `https://management.azure.com${resourceId}?api-version=2021-04-01`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    if (!response.ok) {
      throw new Error('Resource access denied');
    }
  }
}
```

---

### CLI Integration

#### Using Authentication from Python CLI

**Example: Scan Command with Authentication**:

```python
import os
import sys
from typing import Optional
from azure.identity import DeviceCodeCredential
from azure.mgmt.resource import ResourceManagementClient

class AuthenticatedScanner:
    """Scanner with dual-account authentication support"""

    def __init__(self):
        self.source_token = os.environ.get('ATG_SOURCE_TOKEN')
        self.gameboard_token = os.environ.get('ATG_GAMEBOARD_TOKEN')

    def get_source_client(self) -> ResourceManagementClient:
        """Get authenticated Azure client for Source Tenant"""
        if not self.source_token:
            raise ValueError(
                'Source Tenant authentication required. '
                'Please authenticate via UI or set ATG_SOURCE_TOKEN environment variable.'
            )

        # Create credential from token
        credential = TokenCredential(self.source_token)

        # Create Azure client
        client = ResourceManagementClient(
            credential=credential,
            subscription_id=self._get_subscription_id()
        )

        return client

    def scan_resources(self, subscription_id: str):
        """Scan resources in Source Tenant"""
        try:
            client = self.get_source_client()

            # List resources
            resources = list(client.resources.list())

            print(f"Found {len(resources)} resources")

            for resource in resources:
                print(f"- {resource.name} ({resource.type})")

        except ValueError as e:
            print(f"Authentication error: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Scan failed: {e}", file=sys.stderr)
            sys.exit(1)

class TokenCredential:
    """Simple token-based credential for Azure SDK"""

    def __init__(self, token: str):
        self.token = token

    def get_token(self, *scopes, **kwargs):
        """Return token for Azure SDK"""
        return TokenResponse(self.token)

class TokenResponse:
    """Token response for Azure SDK"""

    def __init__(self, token: str):
        self.token = token
        # Extract expiration from JWT
        import jwt
        decoded = jwt.decode(token, options={"verify_signature": False})
        self.expires_on = decoded['exp']

# Usage
if __name__ == '__main__':
    scanner = AuthenticatedScanner()
    scanner.scan_resources(subscription_id='...')
```

#### Retrieving Tokens from Backend

**Example: Token Retrieval Helper**:

```python
import subprocess
import json
from typing import Optional

class TokenManager:
    """Helper for retrieving tokens from backend"""

    def __init__(self, backend_url: str = 'http://localhost:3000'):
        self.backend_url = backend_url

    def get_token(self, tenant_type: str) -> Optional[str]:
        """Get authentication token for specified tenant"""
        try:
            result = subprocess.run(
                ['curl', '-s', f'{self.backend_url}/api/auth/token?tenantType={tenant_type}'],
                capture_output=True,
                text=True,
                check=True
            )

            response = json.loads(result.stdout)
            return response.get('token')
        except subprocess.CalledProcessError as e:
            print(f"Failed to retrieve token: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Invalid response from backend: {e}")
            return None

    def export_to_environment(self) -> None:
        """Export tokens to environment variables"""
        source_token = self.get_token('source')
        gameboard_token = self.get_token('gameboard')

        if source_token:
            os.environ['ATG_SOURCE_TOKEN'] = source_token

        if gameboard_token:
            os.environ['ATG_GAMEBOARD_TOKEN'] = gameboard_token

# Usage
token_manager = TokenManager()
token_manager.export_to_environment()

# Now tokens available in environment
scanner = AuthenticatedScanner()
scanner.scan_resources()
```

---

## Extending the Authentication System

### Adding a Third Tenant

**Scenario**: Support "Target Tenant" in addition to Source and Gameboard.

**Steps**:

1. **Update TypeScript types**:

```typescript
// src/types/auth.ts
export type TenantType = 'source' | 'gameboard' | 'target';

export interface AuthContextValue {
  sourceAuth: AuthState;
  gameboardAuth: AuthState;
  targetAuth: AuthState;  // Add new tenant
  signIn: (tenantType: TenantType) => Promise<void>;
  signOut: (tenantType: TenantType) => Promise<void>;
  getToken: (tenantType: TenantType) => Promise<string | null>;
}
```

2. **Update AuthContext**:

```typescript
// src/context/AuthContext.tsx
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sourceAuth, setSourceAuth] = useState<AuthState>({ status: 'not_authenticated' });
  const [gameboardAuth, setGameboardAuth] = useState<AuthState>({ status: 'not_authenticated' });
  const [targetAuth, setTargetAuth] = useState<AuthState>({ status: 'not_authenticated' });  // Add

  // Add target tenant to all operations
  // ...
};
```

3. **Update TokenStore**:

```typescript
// src/services/TokenStore.ts
const STORAGE_KEYS = {
  source: { /* ... */ },
  gameboard: { /* ... */ },
  target: {  // Add new keys
    accessToken: 'atg_target_access_token',
    refreshToken: 'atg_target_refresh_token',
    expiresAt: 'atg_target_expires_at',
    user: 'atg_target_user',
    tenantId: 'atg_target_tenant_id'
  }
};
```

4. **Update UI**:

```typescript
// src/components/AuthTab.tsx
<TenantCard
  tenantType="target"
  authState={targetAuth}
  onSignIn={() => signIn('target')}
  onSignOut={() => signOut('target')}
/>
```

5. **Update CLI integration**:

```bash
# Export third token
export ATG_TARGET_TOKEN="$(curl -s 'http://localhost:3000/api/auth/token?tenantType=target' | jq -r .token)"
```

### Custom Token Refresh Logic

**Scenario**: Refresh tokens more aggressively (5 minutes before expiration instead of 10).

**Implementation**:

```typescript
// src/context/AuthContext.tsx

useEffect(() => {
  // Check token expiration every 2 minutes (more frequent)
  const interval = setInterval(() => {
    checkAndRefreshTokens();
  }, 2 * 60 * 1000);

  return () => clearInterval(interval);
}, []);

async function checkAndRefreshTokens() {
  for (const tenantType of ['source', 'gameboard'] as const) {
    const auth = tenantType === 'source' ? sourceAuth : gameboardAuth;

    if (auth.status === 'authenticated' && auth.expiresAt) {
      const expiresAt = new Date(auth.expiresAt);
      const now = new Date();
      const minutesUntilExpiry = (expiresAt.getTime() - now.getTime()) / 60000;

      // Refresh if < 5 minutes remaining (changed from 10)
      if (minutesUntilExpiry < 5) {
        try {
          await refreshToken(tenantType);
          console.log(`Token refreshed for ${tenantType} tenant`);
        } catch (error) {
          console.error(`Token refresh failed for ${tenantType}:`, error);
          // Update auth state to expired
          if (tenantType === 'source') {
            setSourceAuth({ status: 'expired', error: 'Token refresh failed' });
          } else {
            setGameboardAuth({ status: 'expired', error: 'Token refresh failed' });
          }
        }
      }
    }
  }
}
```

### Custom Authentication UI

**Scenario**: Replace standard device code modal with custom UI.

**Implementation**:

```typescript
// src/components/CustomAuthModal.tsx
import { useState, useEffect } from 'react';

interface CustomAuthModalProps {
  tenantType: 'source' | 'gameboard';
  onComplete: () => void;
  onCancel: () => void;
}

export function CustomAuthModal({ tenantType, onComplete, onCancel }: CustomAuthModalProps) {
  const [deviceCode, setDeviceCode] = useState<DeviceCodeInfo | null>(null);
  const [qrCode, setQrCode] = useState<string | null>(null);

  useEffect(() => {
    startAuthFlow();
  }, []);

  async function startAuthFlow() {
    // Start device code flow
    const response = await fetch('/api/device-code/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCsrfToken()
      },
      body: JSON.stringify({ tenantType })
    });

    const deviceCodeInfo = await response.json();
    setDeviceCode(deviceCodeInfo);

    // Generate QR code for mobile authentication
    const qrCodeUrl = `https://microsoft.com/devicelogin?code=${deviceCodeInfo.user_code}`;
    const qrCodeImage = await generateQRCode(qrCodeUrl);
    setQrCode(qrCodeImage);

    // Start polling
    pollAuthStatus(deviceCodeInfo);
  }

  async function pollAuthStatus(deviceCodeInfo: DeviceCodeInfo) {
    const interval = setInterval(async () => {
      const response = await fetch(
        `/api/device-code/status?tenantType=${tenantType}&deviceCode=${deviceCodeInfo.device_code}`
      );

      const status = await response.json();

      if (status.status === 'completed') {
        clearInterval(interval);
        onComplete();
      } else if (status.status === 'expired') {
        clearInterval(interval);
        alert('Device code expired');
      }
    }, deviceCodeInfo.interval * 1000);
  }

  return (
    <div className="custom-auth-modal">
      <h2>Authenticate to {tenantType} Tenant</h2>

      {deviceCode && (
        <>
          <div className="auth-methods">
            <div className="method">
              <h3>Option 1: Enter Code</h3>
              <p>Open <a href={deviceCode.verification_uri} target="_blank">this link</a></p>
              <p>Enter code: <strong>{deviceCode.user_code}</strong></p>
            </div>

            <div className="method">
              <h3>Option 2: Scan QR Code</h3>
              {qrCode && <img src={qrCode} alt="QR Code" />}
              <p>Scan with your mobile device</p>
            </div>
          </div>

          <button onClick={onCancel}>Cancel</button>
        </>
      )}
    </div>
  );
}
```

---

## Testing

### Unit Testing Authentication Logic

**Example: Testing AuthManager**:

```typescript
// tests/services/AuthManager.test.ts
import { AuthManager } from '../../src/services/AuthManager';
import { TokenStore } from '../../src/services/TokenStore';

describe('AuthManager', () => {
  let authManager: AuthManager;
  let tokenStore: jest.Mocked<TokenStore>;

  beforeEach(() => {
    tokenStore = {
      getAccessToken: jest.fn(),
      setAccessToken: jest.fn(),
      getRefreshToken: jest.fn(),
      setRefreshToken: jest.fn(),
      clearTokens: jest.fn()
    } as any;

    authManager = new AuthManager(tokenStore);
  });

  describe('validateTokenTenant', () => {
    it('returns true for matching tenant ID', () => {
      const token = createMockToken({ tid: 'tenant-123' });
      const result = authManager.validateTokenTenant(token, 'tenant-123');
      expect(result).toBe(true);
    });

    it('returns false for mismatched tenant ID', () => {
      const token = createMockToken({ tid: 'tenant-123' });
      const result = authManager.validateTokenTenant(token, 'tenant-456');
      expect(result).toBe(false);
    });
  });

  describe('getAccessToken', () => {
    it('returns valid token when not expired', async () => {
      const token = createMockToken({ exp: Date.now() / 1000 + 3600 });
      tokenStore.getAccessToken.mockResolvedValue(token);
      tokenStore.getTokenExpiration.mockResolvedValue(new Date(Date.now() + 3600000));

      const result = await authManager.getAccessToken('source');
      expect(result).toBe(token);
    });

    it('refreshes token when expiring soon', async () => {
      const expiredToken = createMockToken({ exp: Date.now() / 1000 + 300 });
      const newToken = createMockToken({ exp: Date.now() / 1000 + 3600 });

      tokenStore.getAccessToken.mockResolvedValueOnce(expiredToken);
      tokenStore.getTokenExpiration.mockResolvedValue(new Date(Date.now() + 300000));
      tokenStore.getAccessToken.mockResolvedValueOnce(newToken);

      // Mock refresh
      jest.spyOn(authManager, 'refreshAccessToken').mockResolvedValue();

      const result = await authManager.getAccessToken('source');

      expect(authManager.refreshAccessToken).toHaveBeenCalledWith('source');
      expect(result).toBe(newToken);
    });
  });
});

function createMockToken(claims: any): string {
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', typ: 'JWT' })).toString('base64');
  const payload = Buffer.from(JSON.stringify(claims)).toString('base64');
  return `${header}.${payload}.signature`;
}
```

### Integration Testing

**Example: Testing Full Authentication Flow**:

```typescript
// tests/integration/auth-flow.test.ts
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider } from '../../src/context/AuthContext';
import { AuthTab } from '../../src/components/AuthTab';

// Mock backend API
const mockBackend = {
  deviceCodeStart: jest.fn(),
  deviceCodeStatus: jest.fn(),
  signOut: jest.fn()
};

describe('Authentication Flow', () => {
  beforeEach(() => {
    // Setup mock responses
    mockBackend.deviceCodeStart.mockResolvedValue({
      user_code: 'ABCD-1234',
      device_code: 'mock-device-code',
      verification_uri: 'https://microsoft.com/devicelogin',
      expires_in: 900,
      interval: 5
    });

    mockBackend.deviceCodeStatus.mockResolvedValueOnce({ status: 'pending' });
    mockBackend.deviceCodeStatus.mockResolvedValueOnce({ status: 'pending' });
    mockBackend.deviceCodeStatus.mockResolvedValue({
      status: 'completed',
      user: 'user@tenant.com',
      tenantId: 'tenant-123',
      expiresAt: new Date(Date.now() + 3600000).toISOString()
    });
  });

  it('completes full authentication flow', async () => {
    render(
      <AuthProvider>
        <AuthTab />
      </AuthProvider>
    );

    // Click "Sign In"
    const signInButton = screen.getByText('Sign In', { selector: '[data-tenant="source"]' });
    await userEvent.click(signInButton);

    // Modal appears with device code
    await waitFor(() => {
      expect(screen.getByText('ABCD-1234')).toBeInTheDocument();
    });

    // Wait for authentication to complete
    await waitFor(() => {
      expect(screen.getByText('user@tenant.com')).toBeInTheDocument();
    }, { timeout: 20000 });

    // Verify "Sign Out" button appears
    expect(screen.getByText('Sign Out')).toBeInTheDocument();
  });
});
```

### Security Testing

**Example: Testing Token Isolation**:

```typescript
// tests/security/token-isolation.test.ts
import { TokenStore } from '../../src/services/TokenStore';

describe('Token Isolation', () => {
  let tokenStore: TokenStore;

  beforeEach(() => {
    tokenStore = new TokenStore();
  });

  afterEach(async () => {
    await tokenStore.clearTokens('source');
    await tokenStore.clearTokens('gameboard');
  });

  it('isolates Source and Gameboard tokens', async () => {
    // Store tokens for both tenants
    await tokenStore.setAccessToken('source', 'source-token-123');
    await tokenStore.setAccessToken('gameboard', 'gameboard-token-456');

    // Retrieve tokens
    const sourceToken = await tokenStore.getAccessToken('source');
    const gameboardToken = await tokenStore.getAccessToken('gameboard');

    // Verify tokens isolated
    expect(sourceToken).toBe('source-token-123');
    expect(gameboardToken).toBe('gameboard-token-456');
    expect(sourceToken).not.toBe(gameboardToken);
  });

  it('does not leak tokens between tenants', async () => {
    // Store token for Source
    await tokenStore.setAccessToken('source', 'source-token-123');

    // Attempt to retrieve as Gameboard (should fail)
    const gameboardToken = await tokenStore.getAccessToken('gameboard');

    expect(gameboardToken).toBeNull();
  });

  it('clears tokens for single tenant without affecting other', async () => {
    // Store tokens for both
    await tokenStore.setAccessToken('source', 'source-token-123');
    await tokenStore.setAccessToken('gameboard', 'gameboard-token-456');

    // Clear Source tokens
    await tokenStore.clearTokens('source');

    // Verify Source tokens cleared
    const sourceToken = await tokenStore.getAccessToken('source');
    expect(sourceToken).toBeNull();

    // Verify Gameboard tokens still present
    const gameboardToken = await tokenStore.getAccessToken('gameboard');
    expect(gameboardToken).toBe('gameboard-token-456');
  });
});
```

---

## Debugging

### Enable Debug Logging

**Backend**:
```typescript
// Enable verbose logging
process.env.LOG_LEVEL = 'debug';

// Log all authentication events
logger.debug('Device code flow started', { tenantType, deviceCode });
logger.debug('Token retrieved', { tenantType, expiresAt });
logger.debug('Token refreshed', { tenantType });
```

**Frontend**:
```typescript
// Enable debug logging in browser console
localStorage.setItem('debug', 'atg:auth:*');
```

### Inspect Token Claims

**Safely decode JWT** (debugging only):

```typescript
function inspectToken(token: string): any {
  // Decode without verification (debugging only)
  const parts = token.split('.');
  if (parts.length !== 3) {
    throw new Error('Invalid token format');
  }

  const payload = Buffer.from(parts[1], 'base64').toString('utf-8');
  return JSON.parse(payload);
}

// Usage (debugging only)
const token = await getToken('source');
const claims = inspectToken(token);

console.log('Token claims:', {
  user: claims.upn,
  tenantId: claims.tid,
  expiresAt: new Date(claims.exp * 1000),
  scopes: claims.scp
});
```

**WARNING**: Never log full tokens, even in debug mode.

---

## Best Practices

### Security

1. **Never log tokens** (not even substrings)
2. **Always validate tenant ID** before using token
3. **Check token expiration** before every use
4. **Use CSRF protection** on state-changing endpoints
5. **Encrypt tokens at rest** using OS-level encryption

### Performance

1. **Cache tokens in memory** after decryption
2. **Refresh proactively** (before expiration)
3. **Poll device code status** at recommended interval (don't poll faster)
4. **Batch token operations** when possible

### User Experience

1. **Show clear error messages** for authentication failures
2. **Display token expiration** prominently
3. **Provide "Go to Auth Tab" links** from feature-gated pages
4. **Auto-refresh tokens** in background (transparent to user)
5. **Persist authentication** across application restarts

---

## Common Pitfalls

### Pitfall 1: Not Validating Tenant ID

**Problem**:
```typescript
// BAD - No tenant validation
const token = await getToken('source');
await deployToGameboard(token);  // Using wrong tenant token!
```

**Solution**:
```typescript
// GOOD - Validate tenant before use
const token = await getToken('gameboard');
if (!authManager.validateTokenTenant(token, gameboardTenantId)) {
  throw new Error('Token tenant mismatch');
}
await deployToGameboard(token);
```

### Pitfall 2: Polling Too Frequently

**Problem**:
```typescript
// BAD - Polling every 1 second
setInterval(() => checkAuthStatus(), 1000);
```

**Solution**:
```typescript
// GOOD - Use interval from device code response
const deviceCode = await startDeviceCodeFlow();
setInterval(() => checkAuthStatus(), deviceCode.interval * 1000);
```

### Pitfall 3: Not Handling Token Expiration

**Problem**:
```typescript
// BAD - Token might be expired
const token = await getToken('source');
await callAzureAPI(token);  // Might fail if expired
```

**Solution**:
```typescript
// GOOD - Check expiration, refresh if needed
const token = await authManager.getAccessToken('source');  // Auto-refreshes if needed
await callAzureAPI(token);
```

### Pitfall 4: Logging Tokens

**Problem**:
```typescript
// BAD - Token in logs
console.log('Token:', token);
logger.debug('Auth header:', `Bearer ${token}`);
```

**Solution**:
```typescript
// GOOD - Never log tokens
console.log('Authentication successful for user:', user);
logger.debug('Token retrieved', { user, expiresAt });  // No token!
```

---

## Related Documentation

- [User Guide](./USER_GUIDE.md) - End-user authentication instructions
- [Architecture Documentation](./ARCHITECTURE.md) - System design and data flow
- [API Reference](./API_REFERENCE.md) - Complete API endpoint documentation
- [Security Guide](./SECURITY.md) - Security features and compliance
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues and solutions

---

## Contributing

### Reporting Issues

- Use GitHub Issues with "auth" label
- Include reproduction steps
- Attach relevant logs (sanitized)

### Code Contributions

1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Ensure no token logging

### Documentation Contributions

- Follow Diataxis framework
- Use real examples (not foo/bar)
- Test all code examples
- Link related documents

## Support

- **GitHub**: https://github.com/org/azure-tenant-grapher
- **Email**: dev@azuretg.example.com
- **Slack**: #atg-dev
