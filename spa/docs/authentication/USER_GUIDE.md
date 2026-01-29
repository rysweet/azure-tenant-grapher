# Dual-Account Authentication User Guide

**Document Type**: Tutorial + How-To Guide
**Audience**: End users of Azure Tenant Grapher
**Last Updated**: 2026-01-29

## Overview

Azure Tenant Grapher supports authenticating to **two separate Azure tenants** simultaneously:

- **Source Tenant**: The Azure tenant you want to scan and analyze
- **Gameboard Tenant**: The Azure tenant where you want to deploy infrastructure

This guide walks you through authenticating to both tenants using Device Code Flow, which works without requiring Azure CLI installation.

## Prerequisites

- Access to both Azure tenants (Source and Gameboard)
- Appropriate permissions in each tenant:
  - **Source Tenant**: Reader access to resources you want to scan
  - **Gameboard Tenant**: Contributor access to deploy infrastructure
- A web browser on any device (authentication happens via browser)

## Quick Start: First-Time Authentication

### Step 1: Launch Azure Tenant Grapher

```bash
# Start the application
atg-ui
```

The application opens in your default browser at `http://localhost:3000`.

### Step 2: Navigate to Authentication Tab

Click the **"Auth"** tab in the top navigation bar.

You'll see two tenant cards:

```
┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│    Source Tenant                │  │    Gameboard Tenant             │
│                                 │  │                                 │
│    Status: Not Authenticated    │  │    Status: Not Authenticated    │
│                                 │  │                                 │
│    [Sign In]                    │  │    [Sign In]                    │
└─────────────────────────────────┘  └─────────────────────────────────┘
```

### Step 3: Authenticate to Source Tenant

1. **Click "Sign In"** on the Source Tenant card
2. **Device Code Modal appears** showing:
   ```
   To sign in, use a web browser to open the page:
   https://microsoft.com/devicelogin

   And enter the code: ABCD-1234

   [Open Browser] [Copy Code]
   ```

3. **Click "Open Browser"** (or manually navigate to the URL)
4. **Enter the device code** when prompted
5. **Complete authentication** in your browser:
   - Select your Source Tenant account
   - Consent to permissions if prompted
   - Wait for "Authentication successful" message

6. **Return to Azure Tenant Grapher**
   - The modal automatically closes
   - Source Tenant card updates:
     ```
     Status: Authenticated
     User: user@source-tenant.com
     Tenant: 12345678-abcd-...
     Expires: 2026-01-29 15:30 UTC

     [Sign Out]
     ```

### Step 4: Authenticate to Gameboard Tenant

Repeat the same process for the Gameboard Tenant:

1. Click **"Sign In"** on the Gameboard Tenant card
2. Follow device code authentication flow
3. Authenticate with your Gameboard Tenant account

### Step 5: Verify Both Authentications

Both tenant cards now show "Authenticated" status:

```
┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│    Source Tenant                │  │    Gameboard Tenant             │
│                                 │  │                                 │
│    ✓ Authenticated              │  │    ✓ Authenticated              │
│    user@source.com              │  │    user@gameboard.com           │
│                                 │  │                                 │
│    [Sign Out]                   │  │    [Sign Out]                   │
└─────────────────────────────────┘  └─────────────────────────────────┘
```

You're now ready to scan your Source Tenant and deploy to your Gameboard Tenant!

## How Authentication Works

### Device Code Flow

Azure Tenant Grapher uses **Device Code Flow**, which provides several benefits:

- **No Azure CLI required**: Works without installing additional tools
- **Browser-based**: Use any device's browser for authentication
- **Secure**: No passwords stored, only encrypted tokens
- **MFA-compatible**: Supports multi-factor authentication

### Token Storage

After successful authentication:

1. **Access tokens** are obtained (valid for 60 minutes)
2. **Refresh tokens** are obtained (valid for 30 days)
3. All tokens are **encrypted using OS-level storage**:
   - **Windows**: DPAPI (Data Protection API)
   - **macOS**: Keychain
   - **Linux**: Secret Service API / libsecret
4. Tokens are **never logged or displayed** in plain text

### Automatic Token Refresh

The system automatically refreshes your access tokens before they expire:

- Checks token expiration every 5 minutes
- Refreshes tokens when they have < 10 minutes remaining
- You remain authenticated for up to 30 days without re-authenticating

## Common Tasks

### Checking Authentication Status

**Via UI**: Open the Auth tab to see current status for both tenants.

**Via CLI**: Check token status from command line:

```bash
# Check Source Tenant authentication
atg auth status --tenant source

# Check Gameboard Tenant authentication
atg auth status --tenant gameboard

# Check both tenants
atg auth status --all
```

Output:
```
Source Tenant:
  Status: Authenticated
  User: user@source-tenant.com
  Tenant ID: 12345678-abcd-efgh-ijkl-mnopqrstuvwx
  Expires: 2026-01-29 15:30:00 UTC

Gameboard Tenant:
  Status: Authenticated
  User: user@gameboard-tenant.com
  Tenant ID: 87654321-wxyz-abcd-efgh-ijklmnopqrst
  Expires: 2026-01-29 15:35:00 UTC
```

### Signing Out

**Sign out from one tenant**:

1. Click **"Sign Out"** on the respective tenant card
2. Confirm sign-out in the modal
3. Tokens are immediately deleted from secure storage

**Sign out from both tenants**:

```bash
# Sign out from both tenants via CLI
atg auth signout --all
```

**Sign out closes your browser session**: You'll need to re-authenticate next time.

### Re-authenticating After Token Expiration

If your refresh token expires (after 30 days), you'll need to re-authenticate:

1. The tenant card shows: **"Status: Token Expired"**
2. Click **"Sign In"** to start a new authentication flow
3. Complete device code authentication again

### Switching Between Accounts

To use a different account for a tenant:

1. **Sign out** from the current account
2. **Sign in** again
3. **Select the different account** during device code authentication

## Feature Gating

Different features require different authentication:

| Feature | Requires Source Auth | Requires Gameboard Auth |
|---------|---------------------|------------------------|
| **Scan Tab** | ✓ Required | Not required |
| **Visualize Tab** | Not required (uses scan data) | Not required |
| **Deploy Tab** | Not required | ✓ Required |
| **Config Tab** | Not required | Not required |

### Scan Tab Behavior

When you open the **Scan** tab:

- **If Source Tenant authenticated**: Scan controls are enabled
- **If Source Tenant NOT authenticated**:
  ```
  ⚠️ Source Tenant authentication required to scan resources

  [Go to Auth Tab]
  ```

### Deploy Tab Behavior

When you open the **Deploy** tab:

- **If Gameboard Tenant authenticated**: Deploy controls are enabled
- **If Gameboard Tenant NOT authenticated**:
  ```
  ⚠️ Gameboard Tenant authentication required to deploy infrastructure

  [Go to Auth Tab]
  ```

## Security Best Practices

### 1. Use Least-Privilege Accounts

Authenticate with accounts that have **only the permissions needed**:

- **Source Tenant**: Reader role on resource groups to scan
- **Gameboard Tenant**: Contributor role on specific resource groups for deployment

### 2. Sign Out When Finished

Sign out from both tenants when:
- Finishing a work session on a shared computer
- Before closing the application for extended periods
- Switching to different Azure environments

### 3. Monitor Token Expiration

Keep an eye on token expiration times:
- Tokens expire after 60 minutes of inactivity
- Refresh tokens expire after 30 days
- Re-authenticate before starting long-running operations

### 4. Protect Your Device

Since tokens are stored on your device:
- Use full-disk encryption
- Lock your screen when away
- Don't share your user account with others

## Troubleshooting

### "Device code expired" Error

**Problem**: Took longer than 15 minutes to complete authentication.

**Solution**:
1. Close the authentication modal
2. Click "Sign In" again to get a new device code
3. Complete authentication within 15 minutes

### "Invalid tenant" Error

**Problem**: Authenticated to the wrong Azure tenant.

**Solution**:
1. Sign out from the affected tenant
2. Sign in again
3. **Carefully select the correct tenant** during authentication
4. Verify the tenant ID displayed after successful authentication

### "Token refresh failed" Error

**Problem**: Refresh token expired or was revoked.

**Solution**:
1. Sign out from the affected tenant
2. Sign in again to obtain new tokens

### Cannot Open Device Code URL

**Problem**: Browser doesn't open automatically.

**Solution**:
1. **Click "Copy Code"** in the modal
2. **Manually open** https://microsoft.com/devicelogin in any browser
3. **Paste the device code** when prompted

### Authentication Succeeds but Features Still Disabled

**Problem**: Authenticated but Scan/Deploy tabs show "authentication required".

**Solution**:
1. Check the Auth tab to verify authentication status
2. Refresh the browser page (Ctrl+R / Cmd+R)
3. Check browser console for errors (F12)
4. If issue persists, sign out and sign in again

For additional troubleshooting, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

## Advanced Usage

### Using Authentication from CLI

The CLI accepts authentication tokens via environment variable:

```bash
# Export Source Tenant token
export ATG_SOURCE_TOKEN="$(atg auth token --tenant source)"

# Run scan with Source Tenant authentication
atg scan --tenant-id "$SOURCE_TENANT_ID"

# Export Gameboard Tenant token
export ATG_GAMEBOARD_TOKEN="$(atg auth token --tenant gameboard)"

# Run deployment with Gameboard Tenant authentication
atg deploy --config ./deployment-config.json
```

### Programmatic Token Retrieval

Retrieve tokens programmatically for automation:

```python
import subprocess
import json

def get_auth_token(tenant_type: str) -> str:
    """Get authentication token for specified tenant"""
    result = subprocess.run(
        ["atg", "auth", "token", "--tenant", tenant_type],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()

# Use in your automation scripts
source_token = get_auth_token("source")
gameboard_token = get_auth_token("gameboard")
```

## Related Documentation

- [Architecture Documentation](./ARCHITECTURE.md) - System design and data flow
- [API Reference](./API_REFERENCE.md) - Complete API endpoint documentation
- [Security Guide](./SECURITY.md) - Security features and compliance
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues and solutions
- [Developer Guide](./DEVELOPER_GUIDE.md) - Integration with authentication system

## FAQs

**Q: Can I use the same account for both tenants?**
A: Yes, if your account has access to both tenants. Authenticate twice with the same credentials, selecting different tenants during each flow.

**Q: Do I need to re-authenticate every time I restart the application?**
A: No. Tokens are persisted in secure storage and remain valid for up to 30 days (refresh token lifetime).

**Q: Can I authenticate to more than two tenants?**
A: Currently, the system supports exactly two tenants (Source and Gameboard). Additional tenants are not supported.

**Q: What happens if I authenticate to the same tenant for both Source and Gameboard?**
A: This is allowed but not recommended. You'll have separate token storage for each role, which may cause confusion.

**Q: Is my password stored anywhere?**
A: No. Passwords are never stored. Only encrypted OAuth tokens are persisted.

**Q: Can I revoke tokens remotely?**
A: Tokens can be revoked through Azure Portal (Enterprise Applications → Azure Tenant Grapher → Users and groups → [Your User] → Revoke sessions).
