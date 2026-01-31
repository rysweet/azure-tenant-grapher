# Dual-Account Authentication Architecture

**Document Type**: Explanation + Reference
**Audience**: Developers, architects, technical stakeholders
**Last Updated**: 2026-01-29

## Executive Summary

Azure Tenant Grapher implements a **dual-account authentication system** that allows simultaneous authentication to two separate Azure tenants (Source and Gameboard) using OAuth 2.0 Device Code Flow. The architecture provides:

- **Independent authentication flows** for each tenant
- **Secure token storage** using OS-level encryption
- **Automatic token refresh** with zero user intervention
- **Feature gating** based on authentication state
- **No external dependencies** (no Azure CLI required)

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Browser                                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Auth Tab UI                                                  │  │
│  │  ┌────────────────────┐    ┌────────────────────┐           │  │
│  │  │ Source Tenant Card │    │ Gameboard Card     │           │  │
│  │  │  [Sign In]         │    │  [Sign In]         │           │  │
│  │  └────────────────────┘    └────────────────────┘           │  │
│  │                                                               │  │
│  │  AuthLoginModal (Device Code Display)                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (API Calls)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Electron Main Process                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Auth API Endpoints (Express)                                │  │
│  │  • POST /api/device-code/start                              │  │
│  │  • GET  /api/device-code/status                             │  │
│  │  • POST /api/auth/signout                                   │  │
│  │  • GET  /api/auth/token                                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │  AuthManager (Core Logic)                                    │  │
│  │  • Device code flow orchestration                           │  │
│  │  • Token refresh scheduling                                 │  │
│  │  • Token validation & tenant verification                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │  TokenStore (Electron safeStorage)                          │  │
│  │  • OS-level encryption (DPAPI/Keychain/libsecret)          │  │
│  │  • Per-tenant token isolation                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ OAuth 2.0 Device Code Flow
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Microsoft Identity Platform                      │
│  • https://login.microsoftonline.com                               │
│  • https://microsoft.com/devicelogin                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              │ Environment Variables
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Python CLI (atg scan/deploy)                     │
│  • Reads: ATG_SOURCE_TOKEN, ATG_GAMEBOARD_TOKEN                    │
│  • Executes operations with tenant-specific auth                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### Frontend Components (React)

#### 1. AuthTab Component

**Location**: `spa/src/components/AuthTab.tsx`

**Responsibilities**:
- Display authentication status for both tenants
- Render tenant cards with sign-in/sign-out controls
- Trigger authentication flows via AuthContext
- Display user information and token expiration

**Key Features**:
```typescript
interface AuthTabProps {
  // No props - uses AuthContext
}

// State management via AuthContext
const { sourceAuth, gameboardAuth, signIn, signOut } = useAuth();

// Tenant card rendering
<TenantCard
  tenantType="source"
  authState={sourceAuth}
  onSignIn={() => signIn('source')}
  onSignOut={() => signOut('source')}
/>
```

**State Display**:
- Not Authenticated
- Authenticating (during device code flow)
- Authenticated (with user details)
- Token Expired
- Error (with error message)

#### 2. AuthLoginModal Component

**Location**: `spa/src/components/AuthLoginModal.tsx`

**Responsibilities**:
- Display device code and verification URL
- Poll authentication status
- Provide "Open Browser" and "Copy Code" actions
- Handle authentication completion/cancellation

**Device Code Display**:
```typescript
interface DeviceCodeInfo {
  user_code: string;           // e.g., "ABCD-1234"
  verification_uri: string;    // "https://microsoft.com/devicelogin"
  expires_in: number;          // 900 (15 minutes)
  interval: number;            // 5 (polling interval in seconds)
  device_code: string;         // Internal use only (not displayed)
}
```

**Polling Logic**:
```typescript
// Poll every 5 seconds (configurable via device_code.interval)
useEffect(() => {
  const pollInterval = setInterval(async () => {
    const status = await checkAuthStatus(tenantType, deviceCode);
    if (status.completed) {
      closeModal();
      refreshAuthState();
    }
  }, interval * 1000);

  return () => clearInterval(pollInterval);
}, [deviceCode, interval]);
```

#### 3. AuthContext (State Management)

**Location**: `spa/src/context/AuthContext.tsx`

**Responsibilities**:
- Centralized authentication state for both tenants
- API interaction via axios
- Token refresh scheduling
- Auth state persistence

**State Structure**:
```typescript
interface AuthState {
  status: 'not_authenticated' | 'authenticating' | 'authenticated' | 'expired' | 'error';
  user?: string;              // user@tenant.com
  tenantId?: string;          // Azure tenant ID
  expiresAt?: string;         // ISO 8601 timestamp
  error?: string;             // Error message
}

interface AuthContextValue {
  sourceAuth: AuthState;
  gameboardAuth: AuthState;
  signIn: (tenantType: 'source' | 'gameboard') => Promise<void>;
  signOut: (tenantType: 'source' | 'gameboard') => Promise<void>;
  getToken: (tenantType: 'source' | 'gameboard') => Promise<string | null>;
  refreshAuthState: () => Promise<void>;
}
```

**Token Refresh Scheduling**:
```typescript
// Check token expiration every 5 minutes
useEffect(() => {
  const interval = setInterval(() => {
    checkAndRefreshTokens();
  }, 5 * 60 * 1000);

  return () => clearInterval(interval);
}, []);

async function checkAndRefreshTokens() {
  for (const tenantType of ['source', 'gameboard']) {
    const auth = tenantType === 'source' ? sourceAuth : gameboardAuth;

    if (auth.status === 'authenticated' && auth.expiresAt) {
      const expiresAt = new Date(auth.expiresAt);
      const now = new Date();
      const minutesUntilExpiry = (expiresAt.getTime() - now.getTime()) / 60000;

      // Refresh if < 10 minutes remaining
      if (minutesUntilExpiry < 10) {
        await refreshToken(tenantType);
      }
    }
  }
}
```

### Backend Components (Electron + Express)

#### 1. Auth API Endpoints

**Location**: `spa/electron/api/auth.ts`

##### POST `/api/device-code/start`

**Purpose**: Initiate device code authentication flow

**Request**:
```json
{
  "tenantType": "source" | "gameboard"
}
```

**Response**:
```json
{
  "user_code": "ABCD-1234",
  "verification_uri": "https://microsoft.com/devicelogin",
  "expires_in": 900,
  "interval": 5,
  "device_code": "internal-use-only-device-code"
}
```

**Implementation**:
```typescript
app.post('/api/device-code/start', csrfProtection, async (req, res) => {
  const { tenantType } = req.body;

  // Validate tenant type
  if (!['source', 'gameboard'].includes(tenantType)) {
    return res.status(400).json({ error: 'Invalid tenant type' });
  }

  // Initiate device code flow with Microsoft Identity Platform
  const deviceCodeInfo = await authManager.startDeviceCodeFlow(tenantType);

  res.json(deviceCodeInfo);
});
```

##### GET `/api/device-code/status`

**Purpose**: Check authentication status during device code flow

**Query Parameters**:
- `tenantType`: "source" | "gameboard"
- `deviceCode`: Device code from start endpoint

**Response (Pending)**:
```json
{
  "status": "pending"
}
```

**Response (Completed)**:
```json
{
  "status": "completed",
  "user": "user@tenant.com",
  "tenantId": "12345678-abcd-efgh-ijkl-mnopqrstuvwx",
  "expiresAt": "2026-01-29T15:30:00Z"
}
```

**Response (Expired)**:
```json
{
  "status": "expired",
  "error": "Device code expired"
}
```

##### POST `/api/auth/signout`

**Purpose**: Sign out from specified tenant and delete tokens

**Request**:
```json
{
  "tenantType": "source" | "gameboard"
}
```

**Response**:
```json
{
  "success": true
}
```

##### GET `/api/auth/token`

**Purpose**: Retrieve current access token for specified tenant

**Query Parameters**:
- `tenantType`: "source" | "gameboard"

**Response**:
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "expiresAt": "2026-01-29T15:30:00Z"
}
```

**Error Response**:
```json
{
  "error": "Not authenticated"
}
```

#### 2. AuthManager (Core Logic)

**Location**: `spa/electron/services/AuthManager.ts`

**Responsibilities**:
- OAuth 2.0 Device Code Flow orchestration
- Token acquisition and refresh
- Token validation and tenant verification
- Interaction with TokenStore

**Key Methods**:

```typescript
class AuthManager {
  /**
   * Start device code authentication flow
   */
  async startDeviceCodeFlow(tenantType: TenantType): Promise<DeviceCodeInfo> {
    const response = await axios.post(
      'https://login.microsoftonline.com/organizations/oauth2/v2.0/devicecode',
      {
        client_id: config.clientId,
        scope: config.scopes.join(' ')
      }
    );

    // Store device code for polling
    this.pendingDeviceCodes.set(tenantType, response.data.device_code);

    return response.data;
  }

  /**
   * Poll authentication status
   */
  async checkDeviceCodeStatus(
    tenantType: TenantType,
    deviceCode: string
  ): Promise<AuthStatusResponse> {
    try {
      const response = await axios.post(
        'https://login.microsoftonline.com/organizations/oauth2/v2.0/token',
        {
          grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
          client_id: config.clientId,
          device_code: deviceCode
        }
      );

      // Authentication successful
      await this.storeTokens(tenantType, response.data);

      return {
        status: 'completed',
        user: this.extractUserFromToken(response.data.access_token),
        tenantId: this.extractTenantFromToken(response.data.access_token),
        expiresAt: this.calculateExpiration(response.data.expires_in)
      };
    } catch (error) {
      if (error.response?.data?.error === 'authorization_pending') {
        return { status: 'pending' };
      }
      if (error.response?.data?.error === 'expired_token') {
        return { status: 'expired', error: 'Device code expired' };
      }
      throw error;
    }
  }

  /**
   * Refresh access token using refresh token
   */
  async refreshAccessToken(tenantType: TenantType): Promise<void> {
    const refreshToken = await tokenStore.getRefreshToken(tenantType);

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await axios.post(
      'https://login.microsoftonline.com/organizations/oauth2/v2.0/token',
      {
        grant_type: 'refresh_token',
        client_id: config.clientId,
        refresh_token: refreshToken,
        scope: config.scopes.join(' ')
      }
    );

    // Store new tokens (refresh token rotation)
    await this.storeTokens(tenantType, response.data);
  }

  /**
   * Validate token and extract tenant ID
   */
  validateTokenTenant(token: string, expectedTenantId: string): boolean {
    const decoded = jwt.decode(token);

    if (!decoded || typeof decoded !== 'object') {
      return false;
    }

    return decoded.tid === expectedTenantId;
  }

  /**
   * Get current access token
   */
  async getAccessToken(tenantType: TenantType): Promise<string | null> {
    const token = await tokenStore.getAccessToken(tenantType);

    if (!token) {
      return null;
    }

    // Check if token is expired or expiring soon
    const expiresAt = await tokenStore.getTokenExpiration(tenantType);
    const now = new Date();
    const minutesUntilExpiry = (expiresAt.getTime() - now.getTime()) / 60000;

    if (minutesUntilExpiry < 10) {
      // Auto-refresh if expiring soon
      await this.refreshAccessToken(tenantType);
      return await tokenStore.getAccessToken(tenantType);
    }

    return token;
  }
}
```

#### 3. TokenStore (Secure Storage)

**Location**: `spa/electron/services/TokenStore.ts`

**Responsibilities**:
- Secure token storage using Electron safeStorage API
- Per-tenant token isolation
- Token retrieval and deletion

**Storage Keys**:
```typescript
const STORAGE_KEYS = {
  source: {
    accessToken: 'atg_source_access_token',
    refreshToken: 'atg_source_refresh_token',
    expiresAt: 'atg_source_expires_at',
    user: 'atg_source_user',
    tenantId: 'atg_source_tenant_id'
  },
  gameboard: {
    accessToken: 'atg_gameboard_access_token',
    refreshToken: 'atg_gameboard_refresh_token',
    expiresAt: 'atg_gameboard_expires_at',
    user: 'atg_gameboard_user',
    tenantId: 'atg_gameboard_tenant_id'
  }
};
```

**Encryption Implementation**:
```typescript
import { safeStorage } from 'electron';

class TokenStore {
  /**
   * Store access token (encrypted)
   */
  async setAccessToken(tenantType: TenantType, token: string): Promise<void> {
    const key = STORAGE_KEYS[tenantType].accessToken;

    // Encrypt using OS-level storage
    const encrypted = safeStorage.encryptString(token);

    // Store encrypted buffer
    await storage.set(key, encrypted.toString('base64'));
  }

  /**
   * Retrieve access token (decrypted)
   */
  async getAccessToken(tenantType: TenantType): Promise<string | null> {
    const key = STORAGE_KEYS[tenantType].accessToken;
    const encryptedBase64 = await storage.get(key);

    if (!encryptedBase64) {
      return null;
    }

    // Decrypt using OS-level storage
    const encrypted = Buffer.from(encryptedBase64, 'base64');
    const decrypted = safeStorage.decryptString(encrypted);

    return decrypted;
  }

  /**
   * Delete all tokens for tenant
   */
  async clearTokens(tenantType: TenantType): Promise<void> {
    const keys = STORAGE_KEYS[tenantType];

    await Promise.all([
      storage.delete(keys.accessToken),
      storage.delete(keys.refreshToken),
      storage.delete(keys.expiresAt),
      storage.delete(keys.user),
      storage.delete(keys.tenantId)
    ]);
  }
}
```

**OS-Level Encryption**:

| Platform | Encryption Method |
|----------|------------------|
| Windows | DPAPI (Data Protection API) |
| macOS | Keychain |
| Linux | Secret Service API (libsecret) |

## Data Flow Diagrams

### Authentication Flow (Device Code)

```
User                 Frontend              Backend              Microsoft
 │                      │                      │                     │
 │ 1. Click "Sign In"   │                      │                     │
 ├─────────────────────>│                      │                     │
 │                      │ 2. POST /device-code/start                │
 │                      ├─────────────────────>│                     │
 │                      │                      │ 3. Request device code
 │                      │                      ├────────────────────>│
 │                      │                      │ 4. Return device_code
 │                      │                      │<────────────────────┤
 │                      │ 5. Return device_code│                     │
 │                      │<─────────────────────┤                     │
 │ 6. Display modal     │                      │                     │
 │<─────────────────────┤                      │                     │
 │                      │                      │                     │
 │ 7. Open browser & enter code                │                     │
 ├──────────────────────────────────────────────────────────────────>│
 │                      │                      │ 8. Authenticate      │
 │<───────────────────────────────────────────────────────────────────┤
 │                      │                      │                     │
 │                      │ 9. Poll: GET /device-code/status            │
 │                      ├─────────────────────>│                     │
 │                      │                      │ 10. Check status    │
 │                      │                      ├────────────────────>│
 │                      │                      │ 11. Tokens          │
 │                      │                      │<────────────────────┤
 │                      │                      │ 12. Store tokens    │
 │                      │                      │   (encrypted)       │
 │                      │ 13. Status: completed│                     │
 │                      │<─────────────────────┤                     │
 │ 14. Close modal      │                      │                     │
 │<─────────────────────┤                      │                     │
```

### Token Refresh Flow

```
Frontend              Backend              TokenStore         Microsoft
   │                      │                      │                │
   │ 1. Check expiration  │                      │                │
   │   (< 10 min left)    │                      │                │
   │                      │                      │                │
   │ 2. Trigger refresh   │                      │                │
   ├─────────────────────>│                      │                │
   │                      │ 3. Get refresh token │                │
   │                      ├─────────────────────>│                │
   │                      │ 4. Return encrypted  │                │
   │                      │<─────────────────────┤                │
   │                      │ 5. Decrypt token     │                │
   │                      │                      │                │
   │                      │ 6. Request new tokens│                │
   │                      ├───────────────────────────────────────>│
   │                      │ 7. Return new tokens │                │
   │                      │<───────────────────────────────────────┤
   │                      │ 8. Store new tokens  │                │
   │                      ├─────────────────────>│                │
   │                      │ 9. Confirm stored    │                │
   │                      │<─────────────────────┤                │
   │ 10. Refresh complete │                      │                │
   │<─────────────────────┤                      │                │
```

### CLI Token Usage Flow

```
User              Frontend             Backend             TokenStore         Python CLI
 │                   │                    │                     │                │
 │ 1. Authenticate   │                    │                     │                │
 │   (earlier)       │                    │                     │                │
 │                   │                    │ Tokens stored       │                │
 │                   │                    │<───────────────────>│                │
 │                   │                    │                     │                │
 │ 2. Run CLI command│                    │                     │                │
 ├──────────────────────────────────────────────────────────────────────────────>│
 │                   │                    │                     │ 3. Check env   │
 │                   │                    │                     │   ATG_*_TOKEN  │
 │                   │                    │                     │                │
 │                   │                    │ 4. GET /api/auth/token                │
 │                   │                    │<────────────────────────────────────┤
 │                   │                    │ 5. Get token        │                │
 │                   │                    ├────────────────────>│                │
 │                   │                    │ 6. Return encrypted │                │
 │                   │                    │<────────────────────┤                │
 │                   │                    │ 7. Decrypt & return │                │
 │                   │                    ├─────────────────────────────────────>│
 │                   │                    │                     │ 8. Use token   │
 │                   │                    │                     │   for Azure API│
 │ 9. Operation complete                  │                     │                │
 │<───────────────────────────────────────────────────────────────────────────────┤
```

## Security Architecture

### Token Security

**Encryption at Rest**:
- All tokens encrypted using Electron `safeStorage` API
- OS-level encryption (DPAPI/Keychain/libsecret)
- Encryption keys managed by OS, not by application

**Token Isolation**:
- Source and Gameboard tokens stored separately
- No cross-contamination possible
- Each tenant has dedicated storage keys

**Token Validation**:
```typescript
// Before using any token
if (!authManager.validateTokenTenant(token, expectedTenantId)) {
  throw new Error('Token tenant mismatch');
}
```

### API Security

**CSRF Protection**:
```typescript
import csrf from 'csurf';

const csrfProtection = csrf({ cookie: true });

// Applied to all state-changing endpoints
app.post('/api/device-code/start', csrfProtection, handler);
app.post('/api/auth/signout', csrfProtection, handler);
```

**Request Validation**:
```typescript
// Validate tenant type
function validateTenantType(tenantType: string): boolean {
  return ['source', 'gameboard'].includes(tenantType);
}

// Validate tokens before use
function validateToken(token: string): boolean {
  try {
    const decoded = jwt.decode(token);
    return decoded && decoded.exp > Date.now() / 1000;
  } catch {
    return false;
  }
}
```

### Logging Security

**No Token Logging**:
```typescript
// NEVER log tokens (even substrings)
logger.info('Authentication successful', {
  tenantType,
  user: authResult.user,
  // NO TOKEN HERE
});

// Sanitize errors before logging
function sanitizeError(error: any): any {
  const sanitized = { ...error };
  delete sanitized.token;
  delete sanitized.access_token;
  delete sanitized.refresh_token;
  return sanitized;
}
```

## Feature Gating Implementation

### Scan Tab Gating

```typescript
// ScanTab.tsx
const { sourceAuth } = useAuth();

if (sourceAuth.status !== 'authenticated') {
  return (
    <div className="auth-required-message">
      <AlertTriangle />
      <h3>Source Tenant authentication required</h3>
      <p>Please authenticate to your Source Tenant to scan resources.</p>
      <Link to="/auth">Go to Auth Tab</Link>
    </div>
  );
}

// Render scan controls
return <ScanControls />;
```

### Deploy Tab Gating

```typescript
// DeployTab.tsx
const { gameboardAuth } = useAuth();

if (gameboardAuth.status !== 'authenticated') {
  return (
    <div className="auth-required-message">
      <AlertTriangle />
      <h3>Gameboard Tenant authentication required</h3>
      <p>Please authenticate to your Gameboard Tenant to deploy infrastructure.</p>
      <Link to="/auth">Go to Auth Tab</Link>
    </div>
  );
}

// Render deploy controls
return <DeployControls />;
```

## Configuration

### Azure App Registration

**Required Configuration**:
```json
{
  "clientId": "12345678-abcd-efgh-ijkl-mnopqrstuvwx",
  "authority": "https://login.microsoftonline.com/organizations",
  "scopes": [
    "https://management.azure.com/user_impersonation",
    "offline_access",
    "openid",
    "profile"
  ]
}
```

**App Registration Settings**:
- **Supported account types**: Accounts in any organizational directory
- **Authentication → Mobile and desktop applications**:
  - Enable "Public client flows"
- **API permissions**:
  - Azure Service Management: `user_impersonation` (delegated)

### Token Lifetimes

| Token Type | Lifetime | Configurable |
|-----------|----------|--------------|
| Access Token | 60 minutes | No (Microsoft default) |
| Refresh Token | 30 days | Yes (via Azure portal) |
| Device Code | 15 minutes | No (Microsoft default) |

## Performance Considerations

### Token Caching

- Tokens cached in memory after decryption
- Cache invalidated on refresh
- Reduces decryption overhead for frequent API calls

### Polling Optimization

- Device code status polling: every 5 seconds (configurable)
- Token expiration checking: every 5 minutes
- Background token refresh: automatic when < 10 minutes remaining

### Async Operations

All authentication operations are asynchronous:
```typescript
// Non-blocking authentication
async function authenticateTenant(tenantType: TenantType): Promise<void> {
  // UI remains responsive during authentication
  const deviceCode = await authManager.startDeviceCodeFlow(tenantType);

  // Poll in background
  const result = await pollAuthStatus(tenantType, deviceCode.device_code);

  // Update UI when complete
  updateAuthState(tenantType, result);
}
```

## Error Handling

### Error Categories

1. **Network Errors**: Azure API unreachable
2. **Authentication Errors**: Invalid credentials, expired device code
3. **Token Errors**: Invalid/expired tokens, refresh failures
4. **Storage Errors**: Encryption/decryption failures

### Error Propagation

```typescript
try {
  await authManager.startDeviceCodeFlow(tenantType);
} catch (error) {
  if (error.code === 'NETWORK_ERROR') {
    // User-friendly message
    showError('Unable to connect to Microsoft authentication service');
  } else if (error.code === 'INVALID_CLIENT') {
    // Configuration issue
    showError('Application configuration error. Please contact support.');
  } else {
    // Generic error
    showError('Authentication failed. Please try again.');
  }

  // Log detailed error for debugging (sanitized)
  logger.error('Authentication error', sanitizeError(error));
}
```

## Testing Strategy

### Unit Tests

- TokenStore encryption/decryption
- AuthManager token validation
- Token expiration calculation
- CSRF protection

### Integration Tests

- Device code flow end-to-end
- Token refresh flow
- Sign-out flow
- Feature gating logic

### Security Tests

- Token isolation verification
- Tenant validation enforcement
- CSRF token validation
- No token leakage in logs

## Related Documentation

- [User Guide](./USER_GUIDE.md) - End-user authentication instructions
- [API Reference](./API_REFERENCE.md) - Complete API documentation
- [Security Guide](./SECURITY.md) - Security features and compliance
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues
- [Developer Guide](./DEVELOPER_GUIDE.md) - Integration guide for developers
