# Authentication Quick Reference

**Document Type**: Reference (Cheat Sheet)
**Audience**: Developers who need quick answers
**Last Updated**: 2026-01-29

## API Endpoints (Quick Reference)

### Start Authentication

```http
POST /api/device-code/start
Content-Type: application/json
X-CSRF-Token: <token>

{
  "tenantType": "source" | "gameboard"
}
```

**Response**:
```json
{
  "user_code": "ABCD-1234",
  "verification_uri": "https://microsoft.com/devicelogin",
  "device_code": "...",
  "expires_in": 900,
  "interval": 5
}
```

### Check Auth Status

```http
GET /api/device-code/status?tenantType=source&deviceCode=...
```

**Response (Pending)**:
```json
{ "status": "pending" }
```

**Response (Completed)**:
```json
{
  "status": "completed",
  "user": "user@tenant.com",
  "tenantId": "12345678-...",
  "expiresAt": "2026-01-29T15:30:00Z"
}
```

### Get Token

```http
GET /api/auth/token?tenantType=source
```

**Response**:
```json
{
  "token": "eyJ0eXAiOiJKV1Q...",
  "expiresAt": "2026-01-29T15:30:00Z",
  "user": "user@tenant.com",
  "tenantId": "12345678-..."
}
```

### Sign Out

```http
POST /api/auth/signout
Content-Type: application/json
X-CSRF-Token: <token>

{
  "tenantType": "source" | "gameboard"
}
```

---

## React Integration (Quick Reference)

### Use AuthContext

```typescript
import { useAuth } from '../context/AuthContext';

function MyComponent() {
  const { sourceAuth, gameboardAuth, signIn, signOut, getToken } = useAuth();

  // Check status
  if (sourceAuth.status === 'authenticated') {
    console.log(`Signed in as ${sourceAuth.user}`);
  }

  // Sign in
  await signIn('source');

  // Sign out
  await signOut('source');

  // Get token
  const token = await getToken('source');
}
```

### Feature Gating

```typescript
function ProtectedFeature() {
  const { sourceAuth } = useAuth();

  if (sourceAuth.status !== 'authenticated') {
    return <div>Please sign in to Source Tenant</div>;
  }

  return <div>Protected content</div>;
}
```

### Call Azure API

```typescript
const { getToken } = useAuth();

async function callAzure() {
  const token = await getToken('source');

  const response = await fetch('https://management.azure.com/...', {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });

  return await response.json();
}
```

---

## CLI Integration (Quick Reference)

### Export Tokens

```bash
# Both tenants
eval $(curl -s http://localhost:3000/api/auth/token/export)

# Single tenant
export ATG_SOURCE_TOKEN="$(curl -s 'http://localhost:3000/api/auth/token?tenantType=source' | jq -r .token)"
```

### Check Status

```bash
# All tenants
atg auth status --all

# Single tenant
atg auth status --tenant source
```

### Use in CLI Commands

```bash
# Export token first
export ATG_SOURCE_TOKEN="$(curl -s 'http://localhost:3000/api/auth/token?tenantType=source' | jq -r .token)"

# Run command
atg scan --tenant-id "$SOURCE_TENANT_ID"
```

---

## Python Integration (Quick Reference)

### Token-Based Credential

```python
import os
from azure.mgmt.resource import ResourceManagementClient

class TokenCredential:
    def __init__(self, token: str):
        self.token = token

    def get_token(self, *scopes, **kwargs):
        return TokenResponse(self.token)

class TokenResponse:
    def __init__(self, token: str):
        self.token = token
        # Extract expiration from JWT
        import jwt
        decoded = jwt.decode(token, options={"verify_signature": False})
        self.expires_on = decoded['exp']

# Usage
token = os.environ.get('ATG_SOURCE_TOKEN')
credential = TokenCredential(token)
client = ResourceManagementClient(credential, subscription_id='...')
```

---

## TypeScript Types (Quick Reference)

### Request/Response Types

```typescript
// Tenant type
type TenantType = 'source' | 'gameboard';

// Auth state
interface AuthState {
  status: 'not_authenticated' | 'authenticating' | 'authenticated' | 'expired' | 'error';
  user?: string;
  tenantId?: string;
  expiresAt?: string;
  error?: string;
}

// Device code info
interface DeviceCodeInfo {
  user_code: string;
  device_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
  message: string;
}

// Token response
interface TokenResponse {
  token: string;
  expiresAt: string;
  user: string;
  tenantId: string;
}
```

---

## Security Checklist (Quick Reference)

### ✅ DO

- ✅ Validate tenant ID before using token
- ✅ Check token expiration
- ✅ Use CSRF protection on state-changing endpoints
- ✅ Encrypt tokens at rest (OS-level)
- ✅ Refresh tokens proactively (< 10 min remaining)
- ✅ Log authentication events (no sensitive data)

### ❌ DON'T

- ❌ Log tokens (even substrings)
- ❌ Store tokens in localStorage
- ❌ Use tokens from wrong tenant
- ❌ Poll device code faster than recommended interval
- ❌ Skip CSRF token on POST requests
- ❌ Hardcode tenant IDs in code

---

## Token Validation (Quick Reference)

### Validate Before Use

```typescript
import jwt from 'jsonwebtoken';

function validateToken(token: string, expectedTenantId: string): boolean {
  // Decode without verification
  const decoded = jwt.decode(token) as any;

  if (!decoded) return false;

  // Check expiration
  if (decoded.exp < Date.now() / 1000) {
    return false;
  }

  // Check tenant
  if (decoded.tid !== expectedTenantId) {
    return false;
  }

  // Check scope
  const scopes = decoded.scp?.split(' ') || [];
  if (!scopes.includes('https://management.azure.com/user_impersonation')) {
    return false;
  }

  return true;
}
```

---

## Error Codes (Quick Reference)

| HTTP Status | Error Code | Meaning |
|-------------|-----------|---------|
| 400 | `INVALID_REQUEST` | Missing/invalid parameters |
| 401 | `NOT_AUTHENTICATED` | No token found |
| 401 | `TOKEN_EXPIRED` | Token expired |
| 403 | `INVALID_CSRF_TOKEN` | CSRF token missing/invalid |
| 404 | `DEVICE_CODE_NOT_FOUND` | Invalid device code |
| 429 | `RATE_LIMIT_EXCEEDED` | Polling too fast |
| 500 | `AZURE_API_ERROR` | Microsoft API failure |
| 500 | `STORAGE_ERROR` | Token storage failure |

---

## Common Pitfalls (Quick Reference)

### Pitfall 1: Not Validating Tenant

```typescript
// ❌ BAD
const token = await getToken('source');
await deployToGameboard(token);

// ✅ GOOD
const token = await getToken('gameboard');
if (!validateTokenTenant(token, gameboardTenantId)) {
  throw new Error('Token tenant mismatch');
}
await deployToGameboard(token);
```

### Pitfall 2: Logging Tokens

```typescript
// ❌ BAD
console.log('Token:', token);

// ✅ GOOD
console.log('Authentication successful', { user, expiresAt });
```

### Pitfall 3: Polling Too Fast

```typescript
// ❌ BAD
setInterval(() => checkStatus(), 1000);

// ✅ GOOD
const { interval } = deviceCode;
setInterval(() => checkStatus(), interval * 1000);
```

### Pitfall 4: Not Handling Expiration

```typescript
// ❌ BAD
const token = await tokenStore.getAccessToken('source');
await callAPI(token);  // Might be expired

// ✅ GOOD
const token = await authManager.getAccessToken('source');  // Auto-refreshes
await callAPI(token);
```

---

## Debugging Commands (Quick Reference)

### Check Authentication

```bash
# UI authenticated?
atg auth status --all

# CLI has tokens?
echo $ATG_SOURCE_TOKEN
echo $ATG_GAMEBOARD_TOKEN
```

### Inspect Token Claims

```bash
# Get token
TOKEN=$(curl -s 'http://localhost:3000/api/auth/token?tenantType=source' | jq -r .token)

# Decode JWT (debugging only)
echo $TOKEN | cut -d. -f2 | base64 -d | jq .
```

### Enable Debug Logging

```bash
# Backend
export ATG_LOG_LEVEL=debug
atg-ui

# Frontend (browser console)
localStorage.setItem('debug', 'atg:auth:*');
location.reload();
```

### Check Storage

```bash
# Linux/Mac
ls -la ~/.config/azuretg/storage/

# Windows
dir %APPDATA%\azuretg\storage
```

---

## Token Lifetimes (Quick Reference)

| Token Type | Lifetime | Refresh Strategy |
|-----------|----------|-----------------|
| Access Token | 60 minutes | Auto-refresh when < 10 min remaining |
| Refresh Token | 30 days | Rotate on every use (new token issued) |
| Device Code | 15 minutes | Get new code if expired |

---

## Environment Variables (Quick Reference)

| Variable | Purpose | Set By |
|----------|---------|--------|
| `ATG_SOURCE_TOKEN` | Source tenant access token | User/script |
| `ATG_GAMEBOARD_TOKEN` | Gameboard tenant access token | User/script |
| `ATG_LOG_LEVEL` | Logging verbosity (debug/info/warn/error) | User |
| `ATG_PORT` | Backend server port (default: 3000) | User |

---

## Storage Keys (Quick Reference)

### Source Tenant

- `atg_source_access_token` (encrypted)
- `atg_source_refresh_token` (encrypted)
- `atg_source_expires_at`
- `atg_source_user`
- `atg_source_tenant_id`

### Gameboard Tenant

- `atg_gameboard_access_token` (encrypted)
- `atg_gameboard_refresh_token` (encrypted)
- `atg_gameboard_expires_at`
- `atg_gameboard_user`
- `atg_gameboard_tenant_id`

---

## Azure AD Configuration (Quick Reference)

### App Registration Settings

**Required**:
- **Supported account types**: Accounts in any organizational directory
- **Authentication → Mobile and desktop applications**: Enabled
- **Public client flows**: Allowed
- **API permissions**: Azure Service Management (`user_impersonation`)

### App Configuration

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

---

## Testing Commands (Quick Reference)

### Manual Testing

```bash
# 1. Authenticate via UI
# 2. Check status
atg auth status --all

# 3. Export tokens
eval $(curl -s http://localhost:3000/api/auth/token/export)

# 4. Verify tokens exported
echo $ATG_SOURCE_TOKEN | head -c 20

# 5. Run CLI command
atg scan --tenant-id "12345678-..."
```

### Unit Testing

```typescript
// Mock AuthContext
jest.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    sourceAuth: { status: 'authenticated', user: 'test@example.com' },
    gameboardAuth: { status: 'not_authenticated' },
    signIn: jest.fn(),
    signOut: jest.fn(),
    getToken: jest.fn().mockResolvedValue('mock-token')
  })
}));
```

---

## Related Documentation (Quick Links)

- **[User Guide](./USER_GUIDE.md)** - Step-by-step instructions
- **[API Reference](./API_REFERENCE.md)** - Complete API documentation
- **[Developer Guide](./DEVELOPER_GUIDE.md)** - Integration patterns
- **[Security Guide](./SECURITY.md)** - Security features
- **[Troubleshooting](./TROUBLESHOOTING.md)** - Common issues
- **[Architecture](./ARCHITECTURE.md)** - System design

---

## Support

- **Issues**: https://github.com/org/azure-tenant-grapher/issues
- **Email**: support@azuretg.example.com
