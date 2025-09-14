# Security Implementation

This document describes the security measures implemented in Azure Tenant Grapher.

## Overview

Azure Tenant Grapher implements multiple layers of security to protect against common vulnerabilities and ensure safe operation.

## Security Features

### 1. Input Validation and Command Injection Prevention

**Location**: `spa/backend/src/security/input-validator.ts`

- **Command Whitelisting**: Only pre-approved commands can be executed
- **Argument Sanitization**: All arguments are validated against dangerous patterns
- **Path Validation**: Prevents path traversal attacks
- **No Shell Execution**: Commands are executed directly without shell interpretation

**Protected Commands**:
- scan
- generate-spec
- generate-iac
- undeploy
- create-tenant
- threat-model
- config
- cli

### 2. WebSocket Authentication

**Location**: `spa/backend/src/security/auth-middleware.ts`

- **Token-Based Authentication**: Secure token generation and validation
- **Rate Limiting**: 10 requests per minute per user
- **Session Management**: Maximum 5 concurrent sessions per user
- **Heartbeat Mechanism**: Automatic cleanup of stale connections
- **Token Expiry**: 24-hour token lifetime

**Usage**:
```javascript
// Get authentication token
POST /api/auth/token
{
  "userId": "user-id",
  "clientId": "client-id"
}

// Connect with token
const socket = io({
  auth: {
    token: "your-token-here"
  }
});
```

### 3. Secure Credential Management

**Location**: `spa/backend/src/security/credential-manager.ts`

- **Encrypted Storage**: Credentials are encrypted using AES-256-GCM
- **Environment Variables**: Primary source for sensitive configuration
- **No Hardcoded Passwords**: All credentials from environment or encrypted storage
- **Credential Rotation**: Support for rotating encryption keys

**Neo4j Connection**:
- Credentials are never hardcoded
- Uses environment variables or encrypted storage
- Validates credential format before use

### 4. Output Sanitization

- **ANSI Code Removal**: Strips terminal control codes
- **Sensitive Data Redaction**: Automatically redacts passwords, API keys, and secrets
- **XSS Prevention**: Sanitizes output before sending to client

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Neo4j Credentials
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-secure-password

# Azure Credentials
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

# Credential Encryption (Production)
CREDENTIAL_MASTER_KEY=<hex-encoded-32-byte-key>
```

### Generating Secure Keys

```bash
# Generate a secure master key for credential encryption
openssl rand -hex 32
```

## Security Best Practices

### For Developers

1. **Never commit sensitive files**:
   - `.env` files
   - `.credential-key`
   - `.neo4j-credentials.enc`
   - Any `.key`, `.pem`, `.cert`, or `.pfx` files

2. **Use secure credentials**:
   - Generate strong passwords
   - Rotate credentials regularly
   - Use different credentials for each environment

3. **Validate all inputs**:
   - Use InputValidator for all user inputs
   - Never execute raw user input
   - Sanitize output before displaying

### For Deployment

1. **Production Environment**:
   - Set `NODE_ENV=production`
   - Use strong `CREDENTIAL_MASTER_KEY`
   - Enable HTTPS for all connections
   - Use secure WebSocket connections (WSS)

2. **Azure Service Principal**:
   - Grant minimal required permissions
   - Rotate client secrets regularly
   - Monitor access logs

3. **Neo4j Database**:
   - Change default password immediately
   - Use strong authentication
   - Enable encryption in transit
   - Restrict network access

## Security Checklist

- [ ] Changed all default passwords
- [ ] Set strong Neo4j password
- [ ] Configured Azure service principal with minimal permissions
- [ ] Set `CREDENTIAL_MASTER_KEY` in production
- [ ] Enabled HTTPS/WSS in production
- [ ] Reviewed and applied firewall rules
- [ ] Enabled audit logging
- [ ] Set up credential rotation schedule
- [ ] Tested rate limiting
- [ ] Validated input sanitization

## Vulnerability Reporting

If you discover a security vulnerability, please report it to the maintainers privately. Do not create public GitHub issues for security vulnerabilities.

## Security Updates

This application uses the following security-critical dependencies:
- `neo4j-driver`: For database connections
- `socket.io`: For WebSocket communication
- `express`: For HTTP server
- Various Azure SDK packages

Keep these dependencies updated to receive security patches.

## Compliance

This implementation addresses the following security concerns:
- OWASP Top 10 considerations
- Command injection prevention (CWE-78)
- Path traversal prevention (CWE-22)
- Authentication and session management (CWE-287)
- Sensitive data exposure prevention (CWE-200)

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Node.js Security Best Practices](https://nodejs.org/en/docs/guides/security/)
- [Azure Security Best Practices](https://docs.microsoft.com/en-us/azure/security/fundamentals/best-practices-and-patterns)