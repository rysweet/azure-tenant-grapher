# Dual-Account Authentication Security Guide

**Document Type**: Reference + Explanation
**Audience**: Security engineers, compliance teams, developers
**Last Updated**: 2026-01-29

## Overview

This document details the security architecture, threat model, and security best practices for Azure Tenant Grapher's dual-account authentication system.

## Security Architecture

### Defense in Depth Strategy

The authentication system implements multiple layers of security:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Transport Security (HTTPS)                         │
│  • TLS 1.3 for all network communication                    │
│  • Certificate pinning for Azure endpoints                  │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Authentication (OAuth 2.0)                         │
│  • Device Code Flow (no credentials stored)                 │
│  • Multi-factor authentication support                      │
│  • Azure AD security policies enforced                      │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Token Security                                     │
│  • OS-level encryption (DPAPI/Keychain/libsecret)          │
│  • Per-tenant token isolation                               │
│  • Automatic token rotation                                 │
│  • Token validation before every use                        │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Application Security                               │
│  • CSRF protection on all state-changing endpoints          │
│  • Input validation and sanitization                        │
│  • No token logging (even substrings)                       │
│  • Feature gating based on authentication state             │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Audit and Monitoring                               │
│  • Authentication events logged (no sensitive data)         │
│  • Failed authentication tracking                           │
│  • Token usage monitoring                                   │
└─────────────────────────────────────────────────────────────┘
```

## Threat Model

### Assets Protected

1. **Access Tokens**: 60-minute lifetime tokens granting Azure API access
2. **Refresh Tokens**: 30-day lifetime tokens for obtaining new access tokens
3. **User Identity**: Email/UPN and tenant membership
4. **Azure Resources**: Resources accessible via authenticated sessions

### Threat Actors

| Actor Type | Motivation | Capabilities |
|-----------|-----------|--------------|
| **External Attacker** | Data theft, resource access | Network-level attacks, phishing |
| **Malicious Software** | Token theft | Local system access, process injection |
| **Insider Threat** | Unauthorized access | Physical device access |
| **Supply Chain** | Backdoor injection | Compromised dependencies |

### Threats and Mitigations

#### Threat 1: Token Theft from Storage

**Risk**: Attacker gains access to stored tokens on disk.

**Mitigation**:
- Tokens encrypted using OS-level encryption (DPAPI/Keychain/libsecret)
- Encryption keys managed by OS, not accessible to attackers without OS-level credentials
- No plaintext tokens ever written to disk

**Residual Risk**: LOW - Requires OS-level compromise

#### Threat 2: Token Interception (Network)

**Risk**: Man-in-the-middle attack intercepts tokens during transmission.

**Mitigation**:
- All communication uses HTTPS/TLS 1.3
- Certificate validation enforced
- No tokens transmitted except to trusted Azure endpoints

**Residual Risk**: LOW - Requires certificate compromise

#### Threat 3: Cross-Site Request Forgery (CSRF)

**Risk**: Attacker tricks user into making authenticated requests.

**Mitigation**:
- CSRF tokens required on all state-changing endpoints
- SameSite cookie attributes set to 'Strict'
- Origin validation on all requests

**Residual Risk**: LOW - Multiple defenses required to bypass

#### Threat 4: Token Leakage via Logs

**Risk**: Tokens logged and exposed via log files.

**Mitigation**:
- No tokens logged anywhere (even substrings forbidden)
- Sanitization functions strip tokens from error objects before logging
- Log review processes verify no token leakage

**Residual Risk**: VERY LOW - Enforced by code review and testing

#### Threat 5: Tenant Confusion Attack

**Risk**: Token for Tenant A used against Tenant B's resources.

**Mitigation**:
- Token tenant validation before every use
- Per-tenant token storage isolation
- Tenant ID embedded in tokens and verified

**Residual Risk**: VERY LOW - Multiple validation points

#### Threat 6: Refresh Token Theft and Reuse

**Risk**: Attacker steals refresh token and maintains persistent access.

**Mitigation**:
- Refresh token rotation (new refresh token issued on every use)
- Refresh tokens invalidated after 30 days
- Revocation cascade (using stolen refresh token invalidates it for legitimate user)

**Residual Risk**: LOW - Theft detected on next legitimate refresh

#### Threat 7: Device Code Phishing

**Risk**: Attacker tricks user into authenticating their device code instead of legitimate one.

**Mitigation**:
- User education (verify application source)
- Device code displayed prominently with verification URL
- Azure shows application name during authentication

**Residual Risk**: MEDIUM - Depends on user vigilance

## Authentication Security

### OAuth 2.0 Device Code Flow

**Why Device Code Flow?**

Device Code Flow provides security benefits over other OAuth flows:

| Flow Type | Password Handling | MFA Support | CLI-Friendly | Phishing Risk |
|-----------|------------------|-------------|--------------|---------------|
| Device Code | ✅ Never exposed | ✅ Full support | ✅ Yes | 🟡 Medium |
| Resource Owner Password | ❌ Exposed to app | ❌ Limited | ✅ Yes | 🔴 High |
| Authorization Code | ✅ Never exposed | ✅ Full support | ❌ No | 🟡 Medium |
| Client Credentials | N/A (service account) | N/A | ✅ Yes | 🟢 Low |

**Flow Security Properties**:

1. **No Password Handling**: Application never sees user password
2. **MFA Compatible**: Full support for Azure MFA, Conditional Access
3. **User Consent**: Clear consent screen showing requested permissions
4. **Limited Scope**: Tokens limited to specific Azure API scopes
5. **Time-Boxed**: Device codes expire after 15 minutes

### Multi-Factor Authentication (MFA)

**MFA Enforcement**:

Device Code Flow respects Azure AD Conditional Access policies:

- If tenant requires MFA, users must complete MFA during authentication
- MFA state checked by Azure AD, not by application
- No MFA bypass mechanisms in application

**Supported MFA Methods**:
- Microsoft Authenticator app
- SMS text message
- Phone call
- Hardware FIDO2 keys
- Windows Hello for Business

## Token Security

### Token Storage

#### OS-Level Encryption

**Windows (DPAPI)**:
```typescript
// Encryption uses user's Windows credentials
import { safeStorage } from 'electron';

// Encrypt
const plaintext = "access_token_here";
const encrypted = safeStorage.encryptString(plaintext);

// Only same user on same machine can decrypt
const decrypted = safeStorage.decryptString(encrypted);
```

**Security Properties**:
- Encryption key derived from user's Windows login credentials
- Decryption requires same user session
- Protected by Windows security boundary

**macOS (Keychain)**:
```typescript
// Encryption uses macOS Keychain
import { safeStorage } from 'electron';

// Encrypt (stored in Keychain)
const encrypted = safeStorage.encryptString(plaintext);

// Decryption requires keychain access
const decrypted = safeStorage.decryptString(encrypted);
```

**Security Properties**:
- Stored in macOS Keychain with application-specific access control
- Requires user authentication to access Keychain
- Protected by macOS security boundary

**Linux (libsecret)**:
```typescript
// Encryption uses Secret Service API
import { safeStorage } from 'electron';

// Encrypt (stored in keyring)
const encrypted = safeStorage.encryptString(plaintext);

// Decryption requires keyring unlock
const decrypted = safeStorage.decryptString(encrypted);
```

**Security Properties**:
- Stored in GNOME Keyring or KWallet
- Requires keyring unlock (typically on login)
- Protected by Linux security boundary

#### Storage Isolation

**Per-Tenant Storage Keys**:

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

**Isolation Benefits**:
- Source and Gameboard tokens cannot cross-contaminate
- Signing out from one tenant doesn't affect the other
- Separate token lifecycles

### Token Validation

**Before Every Token Use**:

```typescript
async function validateAndUseToken(
  tenantType: 'source' | 'gameboard',
  expectedTenantId: string
): Promise<string> {
  // 1. Retrieve token
  const token = await tokenStore.getAccessToken(tenantType);

  if (!token) {
    throw new SecurityError('No token available');
  }

  // 2. Check expiration
  const expiresAt = await tokenStore.getTokenExpiration(tenantType);
  if (new Date() >= expiresAt) {
    throw new SecurityError('Token expired');
  }

  // 3. Validate token structure (JWT)
  const decoded = jwt.decode(token);
  if (!decoded || typeof decoded !== 'object') {
    throw new SecurityError('Invalid token format');
  }

  // 4. Validate tenant ID
  if (decoded.tid !== expectedTenantId) {
    throw new SecurityError('Token tenant mismatch');
  }

  // 5. Validate scope
  const requiredScopes = ['https://management.azure.com/user_impersonation'];
  const tokenScopes = decoded.scp?.split(' ') || [];

  for (const requiredScope of requiredScopes) {
    if (!tokenScopes.includes(requiredScope)) {
      throw new SecurityError(`Missing required scope: ${requiredScope}`);
    }
  }

  return token;
}
```

### Token Rotation

**Access Token Rotation**:
- Access tokens expire after 60 minutes
- Automatically refreshed when < 10 minutes remaining
- New access token obtained via refresh token

**Refresh Token Rotation**:
- Refresh tokens expire after 30 days
- **New refresh token issued on every use** (rotation)
- Old refresh token immediately invalidated

**Rotation Benefits**:
- Limits damage from token theft
- Stolen refresh token detected on next legitimate use
- Forces re-authentication after 30 days

**Rotation Implementation**:
```typescript
async function refreshAccessToken(tenantType: TenantType): Promise<void> {
  const refreshToken = await tokenStore.getRefreshToken(tenantType);

  // Request new tokens
  const response = await axios.post(
    'https://login.microsoftonline.com/organizations/oauth2/v2.0/token',
    {
      grant_type: 'refresh_token',
      client_id: config.clientId,
      refresh_token: refreshToken,
      scope: config.scopes.join(' ')
    }
  );

  // Store NEW access token and NEW refresh token (rotation)
  await tokenStore.setAccessToken(tenantType, response.data.access_token);
  await tokenStore.setRefreshToken(tenantType, response.data.refresh_token);

  // Old refresh token now invalid
}
```

## Application Security

### CSRF Protection

**Implementation**:

```typescript
import csrf from 'csurf';

// Enable CSRF protection
const csrfProtection = csrf({ cookie: true });

// Apply to all state-changing endpoints
app.post('/api/device-code/start', csrfProtection, handler);
app.post('/api/auth/signout', csrfProtection, handler);

// Read-only endpoints don't require CSRF protection
app.get('/api/auth/status', handler);
app.get('/api/auth/token', handler);
```

**Client Usage**:

```typescript
// 1. Obtain CSRF token
const csrfResponse = await fetch('/api/csrf-token');
const { csrfToken } = await csrfResponse.json();

// 2. Include in requests
await fetch('/api/device-code/start', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken
  },
  body: JSON.stringify({ tenantType: 'source' })
});
```

### Input Validation

**Tenant Type Validation**:

```typescript
function validateTenantType(tenantType: any): tenantType is 'source' | 'gameboard' {
  return tenantType === 'source' || tenantType === 'gameboard';
}

// In endpoints
app.post('/api/device-code/start', (req, res) => {
  const { tenantType } = req.body;

  if (!validateTenantType(tenantType)) {
    return res.status(400).json({
      error: 'Invalid tenant type',
      message: 'tenantType must be "source" or "gameboard"'
    });
  }

  // Proceed with valid tenant type
});
```

**Device Code Validation**:

```typescript
function validateDeviceCode(deviceCode: any): boolean {
  // Device codes are opaque strings from Microsoft
  // Validate format only (don't validate content)
  return typeof deviceCode === 'string' &&
         deviceCode.length > 0 &&
         deviceCode.length < 1000;  // Reasonable upper bound
}
```

### No Token Logging

**Logging Sanitization**:

```typescript
/**
 * Sanitize object for logging (remove all token fields)
 */
function sanitizeForLogging(obj: any): any {
  if (typeof obj !== 'object' || obj === null) {
    return obj;
  }

  const sanitized = Array.isArray(obj) ? [] : {};

  for (const [key, value] of Object.entries(obj)) {
    // Skip token fields entirely
    if (
      key.toLowerCase().includes('token') ||
      key.toLowerCase().includes('password') ||
      key.toLowerCase().includes('secret')
    ) {
      sanitized[key] = '[REDACTED]';
      continue;
    }

    // Recursively sanitize nested objects
    if (typeof value === 'object' && value !== null) {
      sanitized[key] = sanitizeForLogging(value);
    } else {
      sanitized[key] = value;
    }
  }

  return sanitized;
}

// Usage
try {
  await someAuthOperation();
} catch (error) {
  logger.error('Auth operation failed', sanitizeForLogging(error));
}
```

**Forbidden Patterns**:

```typescript
// ❌ NEVER DO THIS
console.log('Token:', token);
console.log('Auth header:', `Bearer ${token}`);
logger.debug('Token substring:', token.slice(0, 20));

// ✅ ALWAYS DO THIS
logger.info('Authentication successful', {
  tenantType,
  user: authResult.user,
  // NO TOKEN FIELDS
});
```

## Network Security

### HTTPS Enforcement

**Production Configuration**:

```typescript
// Force HTTPS in production
if (process.env.NODE_ENV === 'production') {
  app.use((req, res, next) => {
    if (req.headers['x-forwarded-proto'] !== 'https') {
      return res.redirect(301, `https://${req.hostname}${req.url}`);
    }
    next();
  });
}
```

**Certificate Pinning** (for Azure endpoints):

```typescript
import https from 'https';

// Pin Azure certificate
const agent = new https.Agent({
  // Validate certificate matches expected
  checkServerIdentity: (hostname, cert) => {
    if (hostname === 'login.microsoftonline.com') {
      const expectedFingerprint = 'AA:BB:CC:...';
      if (cert.fingerprint !== expectedFingerprint) {
        throw new Error('Certificate mismatch');
      }
    }
  }
});

// Use pinned agent for Azure requests
axios.defaults.httpsAgent = agent;
```

### Rate Limiting

**Device Code Polling**:

```typescript
import rateLimit from 'express-rate-limit';

const deviceCodeLimiter = rateLimit({
  windowMs: 1000, // 1 second
  max: 1,         // 1 request per second
  message: {
    error: 'RATE_LIMIT_EXCEEDED',
    message: 'Too many requests. Please wait before polling again.'
  }
});

app.get('/api/device-code/status', deviceCodeLimiter, handler);
```

## Compliance and Auditing

### Compliance Standards

Azure Tenant Grapher authentication system complies with:

| Standard | Requirement | Implementation |
|----------|------------|----------------|
| **OWASP Top 10** | Broken Authentication | OAuth 2.0, MFA support, token rotation |
| **OWASP Top 10** | Sensitive Data Exposure | OS-level encryption, no token logging |
| **OWASP Top 10** | CSRF | CSRF tokens on state-changing endpoints |
| **NIST 800-63B** | Authenticator Lifecycle | Token rotation, 30-day expiration |
| **NIST 800-63B** | Session Management | Automatic token refresh, secure storage |
| **SOC 2** | Logical Access Controls | Per-tenant isolation, feature gating |
| **GDPR** | Data Minimization | Only necessary user data stored |

### Audit Logging

**Logged Events**:

```typescript
// Authentication started
logger.info('Device code flow started', {
  tenantType: 'source',
  timestamp: new Date().toISOString(),
  // NO USER INFO (user not authenticated yet)
});

// Authentication completed
logger.info('Authentication successful', {
  tenantType: 'source',
  user: 'user@tenant.com',
  tenantId: '12345678-abcd-...',
  timestamp: new Date().toISOString(),
  // NO TOKEN
});

// Authentication failed
logger.warn('Authentication failed', {
  tenantType: 'source',
  error: 'Device code expired',
  timestamp: new Date().toISOString(),
  // NO TOKEN
});

// Token refresh
logger.info('Token refreshed', {
  tenantType: 'source',
  user: 'user@tenant.com',
  expiresAt: '2026-01-29T15:30:00Z',
  timestamp: new Date().toISOString(),
  // NO TOKEN
});

// Sign out
logger.info('User signed out', {
  tenantType: 'source',
  user: 'user@tenant.com',
  timestamp: new Date().toISOString()
});
```

**Not Logged** (Security):
- Access tokens
- Refresh tokens
- Token substrings
- Device codes (after initial creation)

**Log Storage**:
- Logs stored locally (not transmitted)
- Log files have restricted permissions (600)
- Logs rotated daily with 30-day retention

## Security Best Practices

### For Users

1. **Use Strong Azure AD Authentication**:
   - Enable MFA on your Azure AD accounts
   - Use strong, unique passwords
   - Don't share accounts between tenants

2. **Protect Your Device**:
   - Use full-disk encryption
   - Lock screen when away from device
   - Don't run untrusted software

3. **Sign Out When Finished**:
   - Sign out from both tenants when done
   - Don't leave authenticated sessions on shared computers

4. **Monitor Token Expiration**:
   - Check expiration times in Auth tab
   - Re-authenticate before long-running operations

5. **Verify Device Codes**:
   - Only enter device codes from applications you launched
   - Verify application name during Azure authentication

### For Developers

1. **Never Log Tokens**:
   - Use `sanitizeForLogging()` on all logged objects
   - Review logs for accidental token exposure
   - No exceptions - even substrings are forbidden

2. **Always Validate Tokens**:
   - Check expiration before use
   - Validate tenant ID matches expected
   - Verify required scopes present

3. **Handle Token Errors Gracefully**:
   - Don't expose internal token errors to users
   - Log errors without sensitive data
   - Provide clear re-authentication paths

4. **Test Token Rotation**:
   - Verify refresh token rotation works
   - Test expired token handling
   - Verify sign-out clears all tokens

5. **Follow Secure Coding Practices**:
   - Input validation on all endpoints
   - CSRF protection on state-changing operations
   - Rate limiting on polling endpoints

### For Administrators

1. **Configure Conditional Access**:
   - Enforce MFA for all users
   - Limit authentication to trusted devices
   - Require compliant devices

2. **Monitor Authentication Events**:
   - Review Azure AD sign-in logs
   - Alert on suspicious authentication patterns
   - Track token usage patterns

3. **Implement Token Policies**:
   - Configure refresh token lifetime in Azure AD
   - Enable continuous access evaluation
   - Revoke tokens for compromised accounts

4. **Regular Security Reviews**:
   - Audit application permissions
   - Review Conditional Access policies
   - Test incident response procedures

## Security Testing

### Manual Security Tests

1. **Token Storage Security**:
   ```bash
   # Verify tokens encrypted at rest
   # 1. Authenticate
   # 2. Find token storage location
   # 3. Verify files are not plaintext
   cat ~/.config/azuretg/storage.db  # Should be encrypted
   ```

2. **Token Isolation**:
   ```typescript
   // Authenticate to both tenants
   await authenticateTenant('source');
   await authenticateTenant('gameboard');

   // Verify tokens isolated
   const sourceToken = await getToken('source');
   const gameboardToken = await getToken('gameboard');

   assert(sourceToken !== gameboardToken);
   assert(validateTokenTenant(sourceToken, sourceTenantId));
   assert(validateTokenTenant(gameboardToken, gameboardTenantId));
   ```

3. **CSRF Protection**:
   ```bash
   # Attempt request without CSRF token (should fail)
   curl -X POST http://localhost:3000/api/device-code/start \
     -H "Content-Type: application/json" \
     -d '{"tenantType": "source"}'
   # Expected: 403 Forbidden
   ```

4. **Token Validation**:
   ```typescript
   // Attempt to use Source token for Gameboard operation
   const sourceToken = await getToken('source');

   // Should fail validation
   try {
     await deployWithToken(sourceToken, gameboardTenantId);
     assert.fail('Should have rejected wrong tenant token');
   } catch (error) {
     assert(error.message.includes('tenant mismatch'));
   }
   ```

### Automated Security Tests

See `spa/tests/security/auth-security.test.ts` for complete test suite:

- Token encryption verification
- Token isolation tests
- CSRF protection tests
- Token validation tests
- No token logging verification
- Token rotation tests

## Incident Response

### Suspected Token Compromise

**Immediate Actions**:

1. **Revoke Tokens**:
   ```bash
   # Sign out from compromised tenant
   atg auth signout --tenant source
   ```

2. **Revoke in Azure Portal**:
   - Navigate to Azure AD → Enterprise Applications
   - Find "Azure Tenant Grapher"
   - Go to Users and groups → [Compromised User]
   - Click "Revoke sessions"

3. **Re-Authenticate**:
   ```bash
   # Authenticate with fresh tokens
   atg auth signin --tenant source
   ```

4. **Review Audit Logs**:
   - Check Azure AD sign-in logs for unauthorized access
   - Review Azure Resource Manager activity logs
   - Identify any unauthorized resource changes

**Longer-Term Actions**:

1. Reset user password
2. Review Conditional Access policies
3. Enable additional MFA factors
4. Audit all Azure resource changes during compromise window

### Token Storage Compromise

If device itself is compromised:

1. **Revoke all tokens** for user in Azure AD
2. **Reset device** or **re-image OS**
3. **Change user password**
4. **Re-authenticate** on clean device

## Security Contact

For security issues or questions:

- **Security Issues**: Report via GitHub Security Advisories
- **Security Questions**: security@azuretg.example.com
- **Incident Response**: incidents@azuretg.example.com

## Related Documentation

- [User Guide](./USER_GUIDE.md) - Security best practices for users
- [Architecture Documentation](./ARCHITECTURE.md) - Security architecture details
- [API Reference](./API_REFERENCE.md) - API security requirements
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Security-related troubleshooting
- [Developer Guide](./DEVELOPER_GUIDE.md) - Secure development practices
