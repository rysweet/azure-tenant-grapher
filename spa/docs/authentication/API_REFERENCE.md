# Dual-Account Authentication API Reference

**Document Type**: Reference
**Audience**: Developers integrating with authentication system
**Last Updated**: 2026-01-29

## Overview

This document provides complete API reference for the dual-account authentication system. All endpoints are exposed via Express server running in the Electron main process.

**Base URL**: `http://localhost:3000/api`

## Authentication Endpoints

### POST `/api/device-code/start`

Initiates OAuth 2.0 Device Code Flow for specified tenant.

#### Request

**Headers**:
```
Content-Type: application/json
X-CSRF-Token: <csrf-token>
```

**Body**:
```json
{
  "tenantType": "source" | "gameboard"
}
```

**Parameters**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenantType` | string | Yes | Target tenant type ("source" or "gameboard") |

#### Response

**Status**: `200 OK`

**Body**:
```json
{
  "user_code": "ABCD-1234",
  "device_code": "internal-device-code-string",
  "verification_uri": "https://microsoft.com/devicelogin",
  "expires_in": 900,
  "interval": 5,
  "message": "To sign in, open https://microsoft.com/devicelogin and enter the code ABCD-1234"
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `user_code` | string | Code user enters in browser (e.g., "ABCD-1234") |
| `device_code` | string | Internal device code for polling (do not display to user) |
| `verification_uri` | string | URL user opens in browser |
| `expires_in` | number | Device code expiration time in seconds (typically 900 = 15 min) |
| `interval` | number | Recommended polling interval in seconds (typically 5) |
| `message` | string | Human-readable instruction message |

#### Error Responses

**400 Bad Request** - Invalid tenant type:
```json
{
  "error": "Invalid tenant type",
  "message": "tenantType must be 'source' or 'gameboard'"
}
```

**500 Internal Server Error** - Azure API failure:
```json
{
  "error": "Failed to initiate device code flow",
  "message": "Unable to connect to Microsoft Identity Platform"
}
```

#### Example

```typescript
const response = await fetch('/api/device-code/start', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken
  },
  body: JSON.stringify({
    tenantType: 'source'
  })
});

const deviceCodeInfo = await response.json();
console.log(`Enter code: ${deviceCodeInfo.user_code}`);
console.log(`At URL: ${deviceCodeInfo.verification_uri}`);
```

---

### GET `/api/device-code/status`

Checks authentication status during device code flow. Poll this endpoint at the interval specified by `/device-code/start` response.

#### Request

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tenantType` | string | Yes | Target tenant type ("source" or "gameboard") |
| `deviceCode` | string | Yes | Device code from `/device-code/start` response |

**Example URL**:
```
/api/device-code/status?tenantType=source&deviceCode=internal-device-code-string
```

#### Response (Pending)

User has not yet completed authentication in browser.

**Status**: `200 OK`

**Body**:
```json
{
  "status": "pending"
}
```

#### Response (Completed)

User successfully completed authentication.

**Status**: `200 OK`

**Body**:
```json
{
  "status": "completed",
  "user": "user@source-tenant.com",
  "tenantId": "12345678-abcd-efgh-ijkl-mnopqrstuvwx",
  "expiresAt": "2026-01-29T15:30:00Z"
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "completed" - authentication successful |
| `user` | string | Authenticated user's email/UPN |
| `tenantId` | string | Azure tenant ID (GUID) |
| `expiresAt` | string | ISO 8601 timestamp when access token expires |

#### Response (Expired)

Device code expired (typically after 15 minutes).

**Status**: `200 OK`

**Body**:
```json
{
  "status": "expired",
  "error": "Device code expired after 15 minutes"
}
```

#### Error Responses

**400 Bad Request** - Missing or invalid parameters:
```json
{
  "error": "Invalid request",
  "message": "tenantType and deviceCode are required"
}
```

**404 Not Found** - Invalid device code:
```json
{
  "error": "Device code not found",
  "message": "No pending authentication for this device code"
}
```

#### Example (Polling)

```typescript
async function pollAuthStatus(
  tenantType: string,
  deviceCode: string,
  interval: number = 5000
): Promise<AuthResult> {
  while (true) {
    const response = await fetch(
      `/api/device-code/status?tenantType=${tenantType}&deviceCode=${deviceCode}`
    );

    const status = await response.json();

    if (status.status === 'completed') {
      return status;
    }

    if (status.status === 'expired') {
      throw new Error('Device code expired');
    }

    // Wait before polling again
    await new Promise(resolve => setTimeout(resolve, interval));
  }
}
```

---

### POST `/api/auth/signout`

Signs out from specified tenant and deletes all stored tokens.

#### Request

**Headers**:
```
Content-Type: application/json
X-CSRF-Token: <csrf-token>
```

**Body**:
```json
{
  "tenantType": "source" | "gameboard"
}
```

**Parameters**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tenantType` | string | Yes | Tenant to sign out from ("source" or "gameboard") |

#### Response

**Status**: `200 OK`

**Body**:
```json
{
  "success": true,
  "message": "Successfully signed out from source tenant"
}
```

#### Error Responses

**400 Bad Request** - Invalid tenant type:
```json
{
  "error": "Invalid tenant type",
  "message": "tenantType must be 'source' or 'gameboard'"
}
```

**500 Internal Server Error** - Token deletion failure:
```json
{
  "error": "Failed to sign out",
  "message": "Unable to delete stored tokens"
}
```

#### Example

```typescript
await fetch('/api/auth/signout', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken
  },
  body: JSON.stringify({
    tenantType: 'source'
  })
});

console.log('Signed out successfully');
```

---

### GET `/api/auth/token`

Retrieves current access token for specified tenant. **Use with caution** - tokens are sensitive credentials.

#### Request

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tenantType` | string | Yes | Target tenant type ("source" or "gameboard") |

**Example URL**:
```
/api/auth/token?tenantType=source
```

#### Response (Authenticated)

**Status**: `200 OK`

**Body**:
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6Ik1...",
  "expiresAt": "2026-01-29T15:30:00Z",
  "user": "user@source-tenant.com",
  "tenantId": "12345678-abcd-efgh-ijkl-mnopqrstuvwx"
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `token` | string | JWT access token (bearer token for Azure API calls) |
| `expiresAt` | string | ISO 8601 timestamp when token expires |
| `user` | string | Authenticated user's email/UPN |
| `tenantId` | string | Azure tenant ID (GUID) |

#### Response (Not Authenticated)

**Status**: `401 Unauthorized`

**Body**:
```json
{
  "error": "Not authenticated",
  "message": "No valid token found for source tenant"
}
```

#### Error Responses

**400 Bad Request** - Invalid tenant type:
```json
{
  "error": "Invalid tenant type",
  "message": "tenantType must be 'source' or 'gameboard'"
}
```

**401 Unauthorized** - Token expired:
```json
{
  "error": "Token expired",
  "message": "Access token expired. Please re-authenticate."
}
```

#### Security Notes

- **Never log tokens** (even substrings)
- **Use HTTPS** in production
- **Validate tenant ID** before using token
- **Short-lived use only** - don't store tokens in frontend

#### Example

```typescript
async function callAzureAPI(resourceUrl: string) {
  // Get token
  const response = await fetch('/api/auth/token?tenantType=source');

  if (!response.ok) {
    throw new Error('Not authenticated');
  }

  const { token } = await response.json();

  // Use token for Azure API call
  const azureResponse = await fetch(resourceUrl, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });

  return await azureResponse.json();
}
```

---

## CLI Integration Endpoint

### GET `/api/auth/token/export`

Exports authentication tokens as environment variable format for CLI usage.

#### Request

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tenantType` | string | No | Specific tenant ("source" or "gameboard"), or omit for both |
| `format` | string | No | Output format ("env" (default), "json", "yaml") |

**Example URLs**:
```
/api/auth/token/export                              # Both tenants, env format
/api/auth/token/export?tenantType=source            # Source only, env format
/api/auth/token/export?tenantType=source&format=json # Source only, JSON format
```

#### Response (ENV Format)

**Status**: `200 OK`

**Content-Type**: `text/plain`

**Body**:
```bash
export ATG_SOURCE_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."
export ATG_GAMEBOARD_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."
```

#### Response (JSON Format)

**Status**: `200 OK`

**Content-Type**: `application/json`

**Body**:
```json
{
  "source": {
    "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "expiresAt": "2026-01-29T15:30:00Z",
    "tenantId": "12345678-abcd-efgh-ijkl-mnopqrstuvwx"
  },
  "gameboard": {
    "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "expiresAt": "2026-01-29T15:35:00Z",
    "tenantId": "87654321-wxyz-abcd-efgh-ijklmnopqrst"
  }
}
```

#### Example (CLI Usage)

```bash
# Export tokens to environment
eval $(curl -s http://localhost:3000/api/auth/token/export)

# Run CLI command with exported tokens
atg scan --tenant-id "$SOURCE_TENANT_ID"
```

---

## Status and Health Endpoints

### GET `/api/auth/status`

Returns authentication status for both tenants.

#### Request

No parameters required.

**Example URL**:
```
/api/auth/status
```

#### Response

**Status**: `200 OK`

**Body**:
```json
{
  "source": {
    "authenticated": true,
    "user": "user@source-tenant.com",
    "tenantId": "12345678-abcd-efgh-ijkl-mnopqrstuvwx",
    "expiresAt": "2026-01-29T15:30:00Z",
    "expiresInMinutes": 45
  },
  "gameboard": {
    "authenticated": false,
    "error": "Not authenticated"
  }
}
```

**Response Fields (Per Tenant)**:
| Field | Type | Description |
|-------|------|-------------|
| `authenticated` | boolean | Whether tenant is authenticated |
| `user` | string | User email/UPN (if authenticated) |
| `tenantId` | string | Azure tenant ID (if authenticated) |
| `expiresAt` | string | ISO 8601 expiration timestamp (if authenticated) |
| `expiresInMinutes` | number | Minutes until token expires (if authenticated) |
| `error` | string | Error message (if not authenticated) |

#### Example

```typescript
const response = await fetch('/api/auth/status');
const status = await response.json();

if (status.source.authenticated) {
  console.log(`Source: ${status.source.user} (expires in ${status.source.expiresInMinutes} min)`);
} else {
  console.log('Source: Not authenticated');
}

if (status.gameboard.authenticated) {
  console.log(`Gameboard: ${status.gameboard.user} (expires in ${status.gameboard.expiresInMinutes} min)`);
} else {
  console.log('Gameboard: Not authenticated');
}
```

---

## TypeScript Type Definitions

### Request Types

```typescript
/**
 * Device code start request
 */
interface DeviceCodeStartRequest {
  tenantType: 'source' | 'gameboard';
}

/**
 * Sign out request
 */
interface SignOutRequest {
  tenantType: 'source' | 'gameboard';
}
```

### Response Types

```typescript
/**
 * Device code information
 */
interface DeviceCodeInfo {
  user_code: string;           // User enters this code
  device_code: string;         // Backend uses for polling
  verification_uri: string;    // URL user opens
  expires_in: number;          // Expiration in seconds
  interval: number;            // Polling interval in seconds
  message: string;             // Human-readable instructions
}

/**
 * Authentication status (during device code flow)
 */
type AuthStatus =
  | { status: 'pending' }
  | {
      status: 'completed';
      user: string;
      tenantId: string;
      expiresAt: string;
    }
  | {
      status: 'expired';
      error: string;
    };

/**
 * Token response
 */
interface TokenResponse {
  token: string;
  expiresAt: string;
  user: string;
  tenantId: string;
}

/**
 * Sign out response
 */
interface SignOutResponse {
  success: boolean;
  message: string;
}

/**
 * Authentication status for single tenant
 */
interface TenantAuthStatus {
  authenticated: boolean;
  user?: string;
  tenantId?: string;
  expiresAt?: string;
  expiresInMinutes?: number;
  error?: string;
}

/**
 * Overall authentication status
 */
interface AuthStatusResponse {
  source: TenantAuthStatus;
  gameboard: TenantAuthStatus;
}
```

### Error Types

```typescript
/**
 * API error response
 */
interface ApiError {
  error: string;
  message: string;
  details?: any;
}
```

---

## Error Handling

### Standard Error Format

All endpoints return errors in consistent format:

```json
{
  "error": "ERROR_TYPE",
  "message": "Human-readable error description",
  "details": {
    "field": "additional_context"
  }
}
```

### Common Error Codes

| HTTP Status | Error Type | Description |
|-------------|-----------|-------------|
| 400 | `INVALID_REQUEST` | Missing or invalid request parameters |
| 401 | `NOT_AUTHENTICATED` | No valid authentication token found |
| 401 | `TOKEN_EXPIRED` | Access token expired, re-authentication required |
| 403 | `INVALID_CSRF_TOKEN` | CSRF token missing or invalid |
| 404 | `DEVICE_CODE_NOT_FOUND` | Invalid or expired device code |
| 500 | `AZURE_API_ERROR` | Microsoft Identity Platform API failure |
| 500 | `STORAGE_ERROR` | Token storage/retrieval failure |

### Error Handling Example

```typescript
async function authenticateTenant(tenantType: 'source' | 'gameboard') {
  try {
    const response = await fetch('/api/device-code/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken
      },
      body: JSON.stringify({ tenantType })
    });

    if (!response.ok) {
      const error = await response.json();

      switch (response.status) {
        case 400:
          throw new Error(`Invalid request: ${error.message}`);
        case 500:
          throw new Error(`Server error: ${error.message}`);
        default:
          throw new Error(`Unexpected error: ${error.message}`);
      }
    }

    return await response.json();
  } catch (error) {
    console.error('Authentication failed:', error);
    throw error;
  }
}
```

---

## Rate Limiting

### Device Code Polling

**Recommendation**: Poll at the interval specified in `/device-code/start` response (typically 5 seconds).

**Rate Limit**:
- Maximum 1 request per second per tenant
- Exceeding rate limit returns `429 Too Many Requests`

**Response (Rate Limited)**:
```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Please wait before polling again.",
  "retryAfter": 5
}
```

### Token Refresh

**Automatic Refresh**: Backend automatically refreshes tokens when < 10 minutes remaining.

**Manual Refresh**: Not exposed via API (handled internally).

---

## Security Considerations

### CSRF Protection

All state-changing endpoints (`POST`, `DELETE`) require CSRF token:

1. **Obtain CSRF token**:
   ```typescript
   const response = await fetch('/api/csrf-token');
   const { csrfToken } = await response.json();
   ```

2. **Include in requests**:
   ```typescript
   headers: {
     'X-CSRF-Token': csrfToken
   }
   ```

### Token Validation

Before using any token:

1. **Validate expiration**: Check `expiresAt` field
2. **Validate tenant**: Ensure token belongs to correct tenant
3. **Validate scope**: Verify token has required permissions

**Example**:
```typescript
function validateToken(tokenResponse: TokenResponse, expectedTenantId: string): boolean {
  // Check expiration
  const expiresAt = new Date(tokenResponse.expiresAt);
  if (expiresAt < new Date()) {
    return false;
  }

  // Check tenant
  if (tokenResponse.tenantId !== expectedTenantId) {
    return false;
  }

  return true;
}
```

### Token Storage

- **Never store tokens in localStorage** or sessionStorage
- **Never log tokens** (even partial tokens)
- **Use tokens immediately** and discard
- **Let backend manage persistence** (encrypted storage)

---

## Usage Examples

### Complete Authentication Flow

```typescript
import { useState, useEffect } from 'react';

interface AuthState {
  status: 'idle' | 'authenticating' | 'authenticated' | 'error';
  user?: string;
  error?: string;
}

function useAuthentication(tenantType: 'source' | 'gameboard') {
  const [authState, setAuthState] = useState<AuthState>({ status: 'idle' });

  async function signIn() {
    try {
      setAuthState({ status: 'authenticating' });

      // Start device code flow
      const deviceCodeResponse = await fetch('/api/device-code/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': getCsrfToken()
        },
        body: JSON.stringify({ tenantType })
      });

      const deviceCode = await deviceCodeResponse.json();

      // Display device code to user
      displayDeviceCode(deviceCode.user_code, deviceCode.verification_uri);

      // Poll for completion
      const interval = setInterval(async () => {
        const statusResponse = await fetch(
          `/api/device-code/status?tenantType=${tenantType}&deviceCode=${deviceCode.device_code}`
        );

        const status = await statusResponse.json();

        if (status.status === 'completed') {
          clearInterval(interval);
          setAuthState({
            status: 'authenticated',
            user: status.user
          });
        } else if (status.status === 'expired') {
          clearInterval(interval);
          setAuthState({
            status: 'error',
            error: 'Device code expired'
          });
        }
      }, deviceCode.interval * 1000);

    } catch (error) {
      setAuthState({
        status: 'error',
        error: error.message
      });
    }
  }

  async function signOut() {
    await fetch('/api/auth/signout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': getCsrfToken()
      },
      body: JSON.stringify({ tenantType })
    });

    setAuthState({ status: 'idle' });
  }

  return { authState, signIn, signOut };
}
```

### Using Tokens for Azure API Calls

```typescript
async function scanAzureResources() {
  // Get authentication token
  const tokenResponse = await fetch('/api/auth/token?tenantType=source');

  if (!tokenResponse.ok) {
    throw new Error('Not authenticated to Source Tenant');
  }

  const { token, tenantId } = await tokenResponse.json();

  // Call Azure Resource Manager API
  const resourcesResponse = await fetch(
    `https://management.azure.com/subscriptions/{subscriptionId}/resources?api-version=2021-04-01`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    }
  );

  const resources = await resourcesResponse.json();
  return resources;
}
```

---

## Related Documentation

- [User Guide](./USER_GUIDE.md) - End-user authentication instructions
- [Architecture Documentation](./ARCHITECTURE.md) - System design and data flow
- [Security Guide](./SECURITY.md) - Security features and compliance
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common API issues
- [Developer Guide](./DEVELOPER_GUIDE.md) - Integration patterns and best practices
