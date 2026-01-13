# Security Fixes for Azure Tenant Grapher

## Executive Summary

This document describes critical security vulnerabilities identified in the Azure Tenant Grapher application and provides comprehensive fixes. Three Priority 0 (P0) vulnerabilities were identified and addressed:

1. **Command Injection** - Unsanitized user input passed to system commands
2. **Missing WebSocket Authentication** - No authentication or rate limiting on WebSocket connections
3. **Hardcoded Credentials** - Database passwords stored in plaintext

## Vulnerabilities and Fixes

### 1. Command Injection (Critical - P0)

#### Vulnerability Details
- **Location**: `spa/backend/src/server.ts:142`, `spa/main/process-manager.ts:36`
- **Issue**: User-supplied command arguments passed directly to `spawn()` without validation
- **Risk**: Remote code execution, system compromise

#### Fix Implementation
Created `spa/backend/src/security/input-validator.ts`:
- Command whitelist validation (only allowed commands)
- Argument sanitization (remove shell metacharacters)
- Length limits to prevent buffer overflow
- Pattern matching to detect injection attempts
- Never use `shell: true` option in spawn

#### Code Example
```typescript
// BEFORE (Vulnerable)
const childProcess = spawn(uvPath, fullArgs, {
  cwd: projectRoot,
  env: process.env
});

// AFTER (Secure)
const commandValidation = validateCommand(command);
if (!commandValidation.valid) {
  return res.status(400).json({ error: commandValidation.error });
}
const childProcess = spawn(uvPath, fullArgs, {
  cwd: projectRoot,
  env: process.env,
  shell: false // Never use shell
});
```

### 2. WebSocket Authentication Missing (Critical - P0)

#### Vulnerability Details
- **Location**: `spa/backend/src/server.ts:49-67`
- **Issues**:
  - No authentication mechanism
  - No rate limiting
  - No heartbeat/timeout
  - Vulnerable to DoS attacks

#### Fix Implementation
Created `spa/backend/src/security/auth-middleware.ts`:
- Token-based authentication system
- Session management with expiration
- WebSocket authentication middleware
- Heartbeat monitoring (30-second intervals)
- Automatic disconnection for inactive clients

Created `spa/backend/src/security/rate-limiter.ts`:
- Per-operation rate limits
- Client tracking by IP
- Automatic blocking for excessive requests
- Configurable time windows and limits

#### Code Example
```typescript
// BEFORE (Vulnerable)
io.on('connection', (socket) => {
  socket.on('subscribe', (processId) => {
    socket.join(`process-${processId}`);
  });
});

// AFTER (Secure)
io.use(authenticateWebSocket);
io.on('connection', (socket) => {
  socket.on('subscribe', (processId) => {
    if (!checkSocketRateLimit(socket, 'ws:subscribe')) {
      socket.emit('error', { message: 'Rate limit exceeded' });
      return;
    }
    if (!requireSocketAuth(socket)) {
      socket.emit('error', { message: 'Authentication required' });
      return;
    }
    if (!validateProcessId(processId)) {
      socket.emit('error', { message: 'Invalid process ID' });
      return;
    }
    socket.join(`process-${processId}`);
  });
});
```

### 3. Hardcoded/Insecure Credentials (Critical - P0)

#### Vulnerability Details
- **Location**: `spa/backend/src/neo4j-service.ts:59`
- **Issue**: Default password hardcoded in source
- **Risk**: Database compromise, data breach

#### Fix Implementation
Created `spa/backend/src/security/credential-manager.ts`:
- AES-256-GCM encryption for stored credentials
- Environment variable priority
- Encrypted credential files with restricted permissions
- Master key management
- Credential validation and masking

#### Code Example
```typescript
// BEFORE (Vulnerable)
const password = process.env.NEO4J_PASSWORD || 'INSECURE-DEFAULT'; // Example of vulnerable code - DO NOT USE
this.driver = neo4j.driver(uri, neo4j.auth.basic(user, password));

// AFTER (Secure)
const { uri, user, password } = credentialManager.getNeo4jCredentials();
if (!credentialManager.validateCredential(password, 'password')) {
  throw new Error('Invalid Neo4j password format');
}
this.driver = neo4j.driver(uri, neo4j.auth.basic(user, password));
```

## Additional Security Enhancements

### Input Validation
- Process ID validation (UUID format)
- Node ID validation (alphanumeric only)
- Search query sanitization
- File path validation (prevent directory traversal)
- Output sanitization (remove ANSI codes, escape HTML)

### Rate Limiting Configuration
```javascript
const limits = {
  'api:execute': { windowMs: 60000, maxRequests: 10 },   // 10 executions/min
  'api:auth': { windowMs: 300000, maxRequests: 5 },      // 5 logins/5min
  'api:neo4j': { windowMs: 60000, maxRequests: 30 },     // 30 queries/min
  'api:search': { windowMs: 60000, maxRequests: 50 },    // 50 searches/min
  'ws:subscribe': { windowMs: 60000, maxRequests: 20 }   // 20 subscriptions/min
};
```

### Security Headers
```javascript
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Strict-Transport-Security', 'max-age=31536000');
  next();
});
```

## Migration Guide

### Step 1: Install Security Modules
```bash
# Copy the security directory to your backend
cp -r spa/backend/src/security spa/backend/src/
```

### Step 2: Update Environment Variables
```bash
# .env file
NEO4J_PASSWORD=<strong-password>  # Remove default password
AUTH_SECRET=<random-32-byte-hex>   # For session tokens
CREDENTIAL_MASTER_KEY=<random-32-byte-hex>  # For credential encryption
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<sha256-hash-of-password>
```

### Step 3: Generate Secure Credentials
```javascript
// Generate password hash for admin
const { createHash } = require('crypto');
const passwordHash = createHash('sha256').update('your-password').digest('hex');
console.log('ADMIN_PASSWORD_HASH=' + passwordHash);

// Generate random secrets
const { randomBytes } = require('crypto');
console.log('AUTH_SECRET=' + randomBytes(32).toString('hex'));
console.log('CREDENTIAL_MASTER_KEY=' + randomBytes(32).toString('hex'));
```

### Step 4: Update Application Files
Replace the following files with their secure versions:
- `server.ts` → `server-secure.ts`
- `neo4j-service.ts` → `neo4j-service-secure.ts`
- `process-manager.ts` → `process-manager-secure.ts`

### Step 5: Update Client Code for Authentication
```typescript
// Add authentication to API calls
const token = localStorage.getItem('authToken');
fetch('/api/execute', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ command, args })
});

// Add authentication to WebSocket
const socket = io({
  auth: {
    token: localStorage.getItem('authToken')
  }
});

// Handle heartbeat
socket.on('heartbeat-ack', () => {
  // Connection is alive
});
setInterval(() => {
  socket.emit('heartbeat');
}, 30000);
```

## Testing the Security Fixes

### Test Command Injection Prevention
```bash
# These should be rejected:
curl -X POST http://localhost:3001/api/execute \
  -H "Authorization: Bearer <token>" \
  -d '{"command": "collect; rm -rf /", "args": []}'

curl -X POST http://localhost:3001/api/execute \
  -H "Authorization: Bearer <token>" \
  -d '{"command": "collect", "args": ["--file=../../etc/passwd"]}'
```

### Test Authentication
```bash
# Login to get token
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'  # pragma: allowlist secret

# Use token for authenticated requests
curl http://localhost:3001/api/graph \
  -H "Authorization: Bearer <token-from-login>"

# Requests without token should fail
curl http://localhost:3001/api/graph  # Should return 401
```

### Test Rate Limiting
```bash
# Rapid requests should trigger rate limit
for i in {1..20}; do
  curl -X POST http://localhost:3001/api/execute \
    -H "Authorization: Bearer <token>" \
    -d '{"command": "status", "args": []}' &
done
# After 10 requests, should get 429 errors
```

## Security Best Practices

1. **Never disable security features** - Even in development
2. **Rotate credentials regularly** - Especially after any potential exposure
3. **Monitor logs** - Look for authentication failures and rate limit violations
4. **Keep dependencies updated** - Run `npm audit` regularly
5. **Use HTTPS in production** - Never transmit credentials over HTTP
6. **Implement RBAC** - Add role-based access control for different user types
7. **Add audit logging** - Log all sensitive operations with user attribution
8. **Regular security scans** - Use tools like OWASP ZAP or Burp Suite

## Compliance Considerations

- **GDPR**: Implement data encryption at rest and in transit
- **SOC2**: Add audit trails and access controls
- **ISO 27001**: Document security policies and procedures
- **HIPAA**: If handling health data, add additional encryption layers

## Support

For security-related questions or to report vulnerabilities:
- Create a private security advisory on GitHub
- Contact the security team directly
- Never disclose vulnerabilities publicly before fixes are deployed

## Version History

- v1.0.0 - Initial security fixes (2024-01-20)
  - Fixed command injection vulnerability
  - Added WebSocket authentication
  - Implemented secure credential management
  - Added rate limiting
  - Implemented input validation

---

**Security Notice**: These fixes address critical vulnerabilities. Deploy them immediately to all environments running Azure Tenant Grapher.
