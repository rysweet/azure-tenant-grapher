# Dual-Account Authentication Documentation

## Overview

Azure Tenant Grapher supports authenticating to **two separate Azure tenants simultaneously**:

- **Source Tenant**: The Azure tenant you want to scan and analyze
- **Gameboard Tenant**: The Azure tenant where you want to deploy infrastructure

This documentation covers all aspects of the dual-account authentication system, from user guides to security details to developer integration patterns.

## Quick Links

### For Users

- **[User Guide](./USER_GUIDE.md)** - Step-by-step authentication instructions
  - How to authenticate to both tenants
  - Common tasks (sign in, sign out, check status)
  - Feature gating (Scan requires Source, Deploy requires Gameboard)
  - Security best practices

- **[Troubleshooting Guide](./TROUBLESHOOTING.md)** - Solutions to common issues
  - Device code errors
  - Token problems
  - UI issues
  - CLI integration issues

### For Developers

- **[Developer Guide](./DEVELOPER_GUIDE.md)** - Integration patterns and best practices
  - Using AuthContext in React components
  - Backend API integration
  - CLI token usage
  - Testing strategies
  - Common pitfalls

- **[API Reference](./API_REFERENCE.md)** - Complete API documentation
  - Authentication endpoints
  - Request/response formats
  - Error codes
  - TypeScript type definitions

### For Architects & Security Teams

- **[Architecture Documentation](./ARCHITECTURE.md)** - System design and data flow
  - High-level architecture
  - Component breakdown
  - Data flow diagrams
  - Performance considerations

- **[Security Guide](./SECURITY.md)** - Security features and compliance
  - Threat model
  - Defense in depth strategy
  - Token security
  - Compliance standards (OWASP, NIST, SOC 2)
  - Incident response procedures

## Documentation Structure (Diataxis Framework)

This documentation follows the [Diataxis framework](https://diataxis.fr/) for technical documentation:

| Document Type | Purpose | Documents |
|--------------|---------|-----------|
| **Tutorial** | Learning-oriented, step-by-step | User Guide (authentication walkthrough) |
| **How-To Guide** | Task-oriented, problem-solving | User Guide (common tasks), Troubleshooting Guide |
| **Reference** | Information-oriented, facts | API Reference, Security Guide |
| **Explanation** | Understanding-oriented, context | Architecture Documentation, Security Guide |

## Key Features

### Device Code Flow Authentication

- **No Azure CLI required**: Works without additional installations
- **Browser-based**: Authenticate using any device's browser
- **MFA-compatible**: Full support for multi-factor authentication
- **Secure**: No passwords stored, only encrypted tokens

### Dual-Account Support

- **Independent authentication**: Each tenant authenticates separately
- **Token isolation**: Source and Gameboard tokens stored separately
- **Feature gating**: Scan requires Source auth, Deploy requires Gameboard auth

### Security

- **OS-level encryption**: Tokens encrypted using DPAPI/Keychain/libsecret
- **Automatic token refresh**: Transparent refresh before expiration
- **Token validation**: Tenant ID verified before every use
- **No token logging**: Never logs tokens (even substrings)

## Getting Started

### For End Users

1. Start with the **[User Guide](./USER_GUIDE.md)**
2. Follow the "Quick Start: First-Time Authentication" section
3. Authenticate to both tenants
4. Use Scan and Deploy features

### For Developers

1. Read the **[Architecture Documentation](./ARCHITECTURE.md)** for system overview
2. Review the **[API Reference](./API_REFERENCE.md)** for endpoint details
3. Follow the **[Developer Guide](./DEVELOPER_GUIDE.md)** for integration patterns
4. Check the **[Security Guide](./SECURITY.md)** for security requirements

### For Troubleshooting

1. Check **[Troubleshooting Guide](./TROUBLESHOOTING.md)** for your specific issue
2. Follow diagnostic steps in "Quick Diagnostic Steps" section
3. Refer to "Error Messages Reference" for error code meanings

## Common Use Cases

### Use Case 1: Scanning a Source Tenant

**Required Authentication**: Source Tenant only

**Steps**:
1. Authenticate to Source Tenant ([User Guide](./USER_GUIDE.md#step-3-authenticate-to-source-tenant))
2. Navigate to Scan tab
3. Configure scan settings
4. Run scan

**Troubleshooting**: If Scan tab shows "Authentication required", see [Troubleshooting Guide](./TROUBLESHOOTING.md#issue-scan-tab-shows-authentication-required-after-signing-in)

### Use Case 2: Deploying to a Gameboard Tenant

**Required Authentication**: Gameboard Tenant only (Source optional)

**Steps**:
1. Authenticate to Gameboard Tenant ([User Guide](./USER_GUIDE.md#step-4-authenticate-to-gameboard-tenant))
2. Navigate to Deploy tab
3. Configure deployment settings
4. Execute deployment

**Troubleshooting**: If Deploy tab shows "Authentication required", see [Troubleshooting Guide](./TROUBLESHOOTING.md#issue-deploy-tab-requires-authentication-despite-being-signed-in)

### Use Case 3: Full Scan-to-Deploy Workflow

**Required Authentication**: Both Source and Gameboard Tenants

**Steps**:
1. Authenticate to Source Tenant
2. Authenticate to Gameboard Tenant ([User Guide](./USER_GUIDE.md#step-5-verify-both-authentications))
3. Scan Source Tenant resources
4. Visualize and analyze scan results
5. Deploy to Gameboard Tenant

### Use Case 4: CLI Integration

**Required Authentication**: Appropriate tenant(s) for CLI operation

**Steps**:
1. Authenticate via UI ([User Guide](./USER_GUIDE.md))
2. Export tokens to environment ([Developer Guide](./DEVELOPER_GUIDE.md#using-authentication-from-python-cli))
3. Run CLI commands

**Example**:
```bash
# Export tokens
eval $(curl -s http://localhost:3000/api/auth/token/export)

# Run scan
atg scan --tenant-id "$SOURCE_TENANT_ID"

# Run deployment
atg deploy --config ./deployment.json
```

**Troubleshooting**: If CLI shows "Not authenticated", see [Troubleshooting Guide](./TROUBLESHOOTING.md#issue-cli-doesnt-see-tokens)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Auth Tab UI → AuthLoginModal → AuthContext             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS (API Calls)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Electron Main Process                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Auth API → AuthManager → TokenStore (OS Encryption)    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ OAuth 2.0 Device Code Flow
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                Microsoft Identity Platform                      │
└─────────────────────────────────────────────────────────────────┘
```

See **[Architecture Documentation](./ARCHITECTURE.md)** for complete details.

## Security Overview

### Defense in Depth

1. **Transport Security**: HTTPS/TLS 1.3
2. **Authentication**: OAuth 2.0 Device Code Flow, MFA support
3. **Token Security**: OS-level encryption, per-tenant isolation, automatic rotation
4. **Application Security**: CSRF protection, input validation, no token logging
5. **Audit**: Authentication events logged (no sensitive data)

### Compliance

- **OWASP Top 10**: Broken Authentication, Sensitive Data Exposure, CSRF
- **NIST 800-63B**: Authenticator lifecycle, session management
- **SOC 2**: Logical access controls
- **GDPR**: Data minimization

See **[Security Guide](./SECURITY.md)** for complete details.

## API Overview

### Authentication Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/device-code/start` | POST | Start device code authentication |
| `/api/device-code/status` | GET | Check authentication status |
| `/api/auth/signout` | POST | Sign out from tenant |
| `/api/auth/token` | GET | Retrieve access token |
| `/api/auth/status` | GET | Check auth status for both tenants |

See **[API Reference](./API_REFERENCE.md)** for complete details.

## Token Lifecycle

```
1. User clicks "Sign In"
   ↓
2. Backend initiates device code flow with Microsoft
   ↓
3. User enters code in browser and authenticates
   ↓
4. Backend polls Microsoft until authentication complete
   ↓
5. Access token (60 min) and refresh token (30 days) obtained
   ↓
6. Tokens encrypted and stored using OS-level encryption
   ↓
7. Access token automatically refreshed when < 10 minutes remaining
   ↓
8. Refresh token rotated on each use (new refresh token issued)
   ↓
9. After 30 days, refresh token expires → User must re-authenticate
```

## Troubleshooting Decision Tree

```
Issue with authentication?
│
├─ During sign-in flow?
│  │
│  ├─ Device code expired? → Get new code ([Troubleshooting](./TROUBLESHOOTING.md#issue-device-code-expired-error))
│  ├─ Network error? → Check connectivity ([Troubleshooting](./TROUBLESHOOTING.md#issue-authentication-failed-network-error))
│  └─ Wrong tenant? → Sign out and re-authenticate ([Troubleshooting](./TROUBLESHOOTING.md#issue-invalid-tenant-error))
│
├─ Token issues?
│  │
│  ├─ Token expired? → Re-authenticate ([Troubleshooting](./TROUBLESHOOTING.md#issue-token-refresh-failed))
│  ├─ Token tenant mismatch? → Sign in to correct tenant ([Troubleshooting](./TROUBLESHOOTING.md#issue-token-tenant-mismatch))
│  └─ Token decryption failed? → Clear and re-authenticate ([Troubleshooting](./TROUBLESHOOTING.md#issue-token-decryption-failed))
│
└─ Feature still disabled?
   │
   ├─ Scan tab disabled? → Check Source auth ([Troubleshooting](./TROUBLESHOOTING.md#issue-scan-tab-shows-authentication-required-after-signing-in))
   └─ Deploy tab disabled? → Check Gameboard auth ([Troubleshooting](./TROUBLESHOOTING.md#issue-deploy-tab-requires-authentication-despite-being-signed-in))
```

## FAQ

**Q: Do I need to authenticate every time I restart the application?**
A: No. Tokens are persisted in secure storage and remain valid for up to 30 days (refresh token lifetime).

**Q: Can I use the same account for both Source and Gameboard?**
A: Yes, if your account has access to both tenants. Authenticate twice, selecting different tenants during each flow.

**Q: What happens if my token expires during a long-running operation?**
A: Tokens are automatically refreshed in the background when they have < 10 minutes remaining. Long operations should complete successfully.

**Q: Can I revoke tokens remotely?**
A: Yes, via Azure Portal: Enterprise Applications → Azure Tenant Grapher → Users → [Your User] → Revoke sessions.

**Q: Is my password stored anywhere?**
A: No. Passwords are never stored. Only OAuth tokens are persisted (encrypted).

**Q: How do I know which tenant I'm authenticated to?**
A: Check the Auth tab in the UI, or run `atg auth status --all` in CLI. Both show tenant ID for verification.

**Q: Can I authenticate to more than two tenants?**
A: Currently, the system supports exactly two tenants (Source and Gameboard). See [Developer Guide](./DEVELOPER_GUIDE.md#adding-a-third-tenant) for extension instructions.

## Glossary

- **Source Tenant**: The Azure tenant you want to scan and analyze
- **Gameboard Tenant**: The Azure tenant where you want to deploy infrastructure
- **Device Code Flow**: OAuth 2.0 authentication flow for devices without browsers
- **Access Token**: Short-lived token (60 min) for Azure API calls
- **Refresh Token**: Long-lived token (30 days) for obtaining new access tokens
- **Token Rotation**: Issuing new refresh token on each use (invalidates old one)
- **Feature Gating**: Requiring authentication for specific features
- **OS-Level Encryption**: Using operating system's secure storage (DPAPI/Keychain/libsecret)

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-29 | Initial documentation for dual-account authentication feature |

## Contributing to Documentation

Contributions welcome! See main repository [CONTRIBUTING.md](../../../CONTRIBUTING.md).

### Documentation Standards

- Follow [Diataxis framework](https://diataxis.fr/)
- Use real examples (not foo/bar)
- Test all code examples
- Link related documents
- Update this README when adding new documents

## Support

- **GitHub Issues**: https://github.com/org/azure-tenant-grapher/issues
- **Documentation Site**: https://docs.azuretg.example.com
- **Community Forum**: https://community.azuretg.example.com
- **Email**: support@azuretg.example.com

### Security Issues

**Do NOT post security issues publicly**. Report via:

- GitHub Security Advisories (private)
- Email: security@azuretg.example.com

## License

This documentation is part of Azure Tenant Grapher and is licensed under [LICENSE](../../../LICENSE).

---

**Last Updated**: 2026-01-29
**Maintained By**: Azure Tenant Grapher Team
