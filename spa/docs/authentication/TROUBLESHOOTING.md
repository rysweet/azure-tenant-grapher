# Dual-Account Authentication Troubleshooting Guide

**Document Type**: How-To Guide + Reference
**Audience**: End users, support teams, developers
**Last Updated**: 2026-01-29

## Overview

This guide provides solutions for common authentication issues in Azure Tenant Grapher's dual-account authentication system.

## Quick Diagnostic Steps

Before diving into specific issues, follow these quick diagnostic steps:

1. **Check Authentication Status**:
   ```bash
   atg auth status --all
   ```

2. **Check Browser Console** (F12):
   - Look for error messages
   - Check Network tab for failed API calls

3. **Check Backend Logs**:
   ```bash
   # View authentication logs
   tail -f ~/.config/azuretg/logs/auth.log
   ```

4. **Verify Network Connectivity**:
   ```bash
   # Test Azure endpoint reachability
   curl -I https://login.microsoftonline.com
   ```

## Common Issues

### Authentication Issues

#### Issue: "Device code expired" Error

**Symptoms**:
- Authentication modal shows "Device code expired"
- Error appears after 15+ minutes of inactivity

**Cause**: Device codes expire after 15 minutes if not used.

**Solution**:

1. Close the authentication modal
2. Click "Sign In" again to get a new device code
3. Complete authentication within 15 minutes

**Prevention**:
- Complete authentication promptly after clicking "Sign In"
- Don't leave device code modal open for extended periods

---

#### Issue: "Invalid tenant" Error

**Symptoms**:
- Authentication completes but shows "Invalid tenant"
- Token validation fails with tenant mismatch

**Cause**: Authenticated to wrong Azure tenant during device code flow.

**Solution**:

1. Sign out from the affected tenant:
   ```bash
   atg auth signout --tenant source
   ```

2. Sign in again:
   ```bash
   atg auth signin --tenant source
   ```

3. **During authentication**, carefully select the correct tenant:
   - Azure shows tenant dropdown during sign-in
   - Verify tenant name/domain before confirming

4. Verify correct tenant after authentication:
   ```bash
   atg auth status --tenant source
   ```
   - Check that "Tenant ID" matches your expected tenant

**Prevention**:
- Note your tenant IDs beforehand
- Double-check tenant selection during authentication

---

#### Issue: "Authentication failed - network error"

**Symptoms**:
- Authentication fails immediately
- Error message mentions network connectivity

**Cause**: Cannot reach Microsoft Identity Platform.

**Solution**:

1. **Check internet connectivity**:
   ```bash
   ping login.microsoftonline.com
   ```

2. **Check proxy settings** (if behind corporate proxy):
   ```bash
   # Set proxy environment variables
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=http://proxy.company.com:8080
   ```

3. **Check firewall rules**:
   - Ensure outbound HTTPS (443) allowed
   - Whitelist: `*.microsoftonline.com`, `*.microsoft.com`

4. **Try again**:
   ```bash
   atg auth signin --tenant source
   ```

**Prevention**:
- Configure proxy settings before launching application
- Ensure firewall rules allow Azure endpoints

---

#### Issue: "Token refresh failed"

**Symptoms**:
- Authentication worked initially
- Now shows "Token expired" or "Refresh failed"

**Cause**: Refresh token expired (after 30 days) or revoked.

**Solution**:

1. Sign out and sign in again:
   ```bash
   atg auth signout --tenant source
   atg auth signin --tenant source
   ```

2. If issue persists, check Azure AD:
   - Navigate to Azure Portal → Azure AD
   - Check if Conditional Access policies changed
   - Verify account not disabled

**Prevention**:
- Re-authenticate every 30 days (before refresh token expires)
- Monitor token expiration in Auth tab

---

#### Issue: "Authorization_Pending" Never Completes

**Symptoms**:
- Device code entered in browser
- Authentication modal stuck polling forever
- Status never changes from "Authenticating"

**Cause**: Authentication not completed in browser, or browser error.

**Solution**:

1. **Check browser authentication**:
   - Open https://microsoft.com/devicelogin in browser
   - Verify you completed authentication
   - Look for "You have signed in" confirmation message

2. **If authentication incomplete**:
   - Complete authentication in browser
   - Wait up to 30 seconds for modal to update

3. **If authentication complete but modal stuck**:
   - Close authentication modal
   - Refresh Auth tab page (Ctrl+R / Cmd+R)
   - Check authentication status - may already be complete

4. **If still stuck**:
   - Restart application
   - Sign in again with new device code

---

#### Issue: "User canceled the authentication flow"

**Symptoms**:
- Authentication fails with "User canceled" error
- Didn't intentionally cancel

**Cause**: Closed browser tab or clicked "Cancel" in Azure consent screen.

**Solution**:

1. Sign in again:
   ```bash
   atg auth signin --tenant source
   ```

2. **Complete all authentication steps**:
   - Enter device code
   - Select correct account
   - Accept permissions consent screen
   - Wait for "You have signed in" confirmation

**Prevention**:
- Don't close browser tabs during authentication
- Review and accept consent screen

---

### Token Issues

#### Issue: "No valid token found"

**Symptoms**:
- Feature shows "Authentication required"
- Auth tab shows "Not Authenticated"

**Cause**: No tokens stored, or tokens deleted.

**Solution**:

1. Authenticate to required tenant:
   ```bash
   # For Scan feature
   atg auth signin --tenant source

   # For Deploy feature
   atg auth signin --tenant gameboard
   ```

2. Verify authentication:
   ```bash
   atg auth status --all
   ```

---

#### Issue: "Token tenant mismatch"

**Symptoms**:
- Authentication successful
- Operations fail with "Token validation failed"
- Logs show "Tenant ID mismatch"

**Cause**: Using token from wrong tenant for operation.

**Root Cause Analysis**:

```bash
# Check which tenant you're authenticated to
atg auth status --all

# Verify tenant IDs
# Source Tenant ID: 12345678-abcd-...
# Gameboard Tenant ID: 87654321-wxyz-...
```

**Solution**:

1. Sign out from affected tenant:
   ```bash
   atg auth signout --tenant source
   ```

2. Sign in to correct tenant:
   ```bash
   atg auth signin --tenant source
   ```

3. During authentication, **verify tenant selection**:
   - Azure shows tenant name in sign-in screen
   - Double-check before proceeding

---

#### Issue: "Token decryption failed"

**Symptoms**:
- Authentication succeeded previously
- Now shows "Cannot retrieve token" or "Decryption failed"

**Cause**: OS-level encryption keys changed (user password change, keychain corruption).

**Solution**:

1. Sign out (clear corrupted tokens):
   ```bash
   atg auth signout --all
   ```

2. Sign in again (new tokens):
   ```bash
   atg auth signin --tenant source
   atg auth signin --tenant gameboard
   ```

3. **macOS-specific**: If using Keychain:
   ```bash
   # Reset Keychain (if corrupted)
   security delete-generic-password -s "Azure Tenant Grapher"
   ```

4. **Windows-specific**: If using DPAPI:
   ```powershell
   # Clear token storage
   Remove-Item -Path "$env:APPDATA\azuretg\storage.db"
   ```

**Prevention**:
- After changing OS password, re-authenticate
- Backup tokens not possible (encrypted to specific user/machine)

---

### UI Issues

#### Issue: Authentication Modal Won't Open

**Symptoms**:
- Click "Sign In" button
- No modal appears
- No error message

**Cause**: JavaScript error or modal state corruption.

**Solution**:

1. **Check browser console** (F12):
   - Look for JavaScript errors
   - Note error message

2. **Refresh the page**:
   - Press Ctrl+R (Windows/Linux) or Cmd+R (Mac)
   - Try signing in again

3. **Clear browser cache**:
   ```bash
   # Or via browser: Ctrl+Shift+Delete
   ```

4. **Restart application**:
   ```bash
   # Stop application
   # Start again
   atg-ui
   ```

---

#### Issue: Device Code Not Displayed

**Symptoms**:
- Authentication modal opens
- Device code field empty or shows "Loading..."
- Never shows actual code

**Cause**: Backend API call failed.

**Solution**:

1. **Check backend logs**:
   ```bash
   tail -f ~/.config/azuretg/logs/auth.log
   ```
   - Look for errors during device code generation

2. **Check network connectivity**:
   ```bash
   curl -I https://login.microsoftonline.com
   ```

3. **Restart backend**:
   ```bash
   # Restart application
   atg-ui
   ```

4. **Try again**:
   - Close modal
   - Click "Sign In" again

---

#### Issue: "Copy Code" Button Doesn't Work

**Symptoms**:
- Click "Copy Code" button
- Code not copied to clipboard

**Cause**: Clipboard API permission denied or browser limitation.

**Solution**:

1. **Manually copy code**:
   - Select device code text with mouse
   - Press Ctrl+C (Windows/Linux) or Cmd+C (Mac)

2. **Grant clipboard permission** (if browser prompts):
   - Click "Allow" when browser asks for clipboard access

3. **Use keyboard shortcut**:
   - Tab to device code text
   - Press Ctrl+A, then Ctrl+C

---

#### Issue: "Open Browser" Button Opens Wrong Browser

**Symptoms**:
- Click "Open Browser"
- Wrong browser opens (not default)

**Cause**: OS default browser setting incorrect.

**Solution**:

1. **Set correct default browser**:

   **Windows**:
   ```
   Settings → Apps → Default apps → Web browser
   ```

   **macOS**:
   ```
   System Preferences → General → Default web browser
   ```

   **Linux**:
   ```bash
   xdg-settings set default-web-browser firefox.desktop
   ```

2. **Or manually open URL**:
   - Copy device code
   - Open preferred browser
   - Navigate to https://microsoft.com/devicelogin
   - Paste code

---

### Feature Gating Issues

#### Issue: Scan Tab Shows "Authentication Required" After Signing In

**Symptoms**:
- Successfully authenticated to Source Tenant
- Scan tab still disabled
- Shows "Authentication required" message

**Cause**: Frontend auth state not updated.

**Solution**:

1. **Refresh auth state**:
   - Navigate away from Scan tab
   - Navigate back to Scan tab

2. **Refresh browser**:
   - Press Ctrl+R (Windows/Linux) or Cmd+R (Mac)

3. **Check auth status**:
   ```bash
   atg auth status --tenant source
   ```
   - Verify "Status: Authenticated"

4. **If still not working**:
   ```bash
   # Sign out and sign in again
   atg auth signout --tenant source
   atg auth signin --tenant source
   ```

---

#### Issue: Deploy Tab Requires Authentication Despite Being Signed In

**Symptoms**:
- Successfully authenticated to Gameboard Tenant
- Deploy tab still disabled

**Cause**: Same as Scan tab issue above.

**Solution**: Follow same steps as "Scan Tab Shows Authentication Required" above, but for Gameboard Tenant.

---

### CLI Integration Issues

#### Issue: CLI Doesn't See Tokens

**Symptoms**:
- Authenticated via UI
- CLI commands fail with "Not authenticated"

**Cause**: Environment variables not set.

**Solution**:

1. **Export tokens to environment**:
   ```bash
   # Export both tenants
   eval $(curl -s http://localhost:3000/api/auth/token/export)

   # Or export individually
   export ATG_SOURCE_TOKEN="$(curl -s 'http://localhost:3000/api/auth/token?tenantType=source' | jq -r .token)"
   export ATG_GAMEBOARD_TOKEN="$(curl -s 'http://localhost:3000/api/auth/token?tenantType=gameboard' | jq -r .token)"
   ```

2. **Verify environment variables set**:
   ```bash
   echo $ATG_SOURCE_TOKEN
   # Should output token (long string starting with "eyJ...")
   ```

3. **Run CLI command**:
   ```bash
   atg scan --tenant-id "$SOURCE_TENANT_ID"
   ```

---

#### Issue: "Token expired" in CLI After Authenticating

**Symptoms**:
- UI shows authenticated
- CLI fails with "Token expired"

**Cause**: Token expired between exporting and using.

**Solution**:

1. **Check token expiration**:
   ```bash
   atg auth status --tenant source
   # Look at "Expires" time
   ```

2. **Export tokens immediately before use**:
   ```bash
   # Export and use in same command
   ATG_SOURCE_TOKEN="$(curl -s 'http://localhost:3000/api/auth/token?tenantType=source' | jq -r .token)" atg scan
   ```

3. **If token genuinely expired**:
   - Tokens auto-refresh in UI
   - Re-export tokens:
     ```bash
     eval $(curl -s http://localhost:3000/api/auth/token/export)
     ```

---

### Connectivity Issues

#### Issue: "ECONNREFUSED" When Calling Auth API

**Symptoms**:
- Error: "connect ECONNREFUSED 127.0.0.1:3000"
- Cannot reach authentication endpoints

**Cause**: Backend server not running.

**Solution**:

1. **Start backend**:
   ```bash
   atg-ui
   ```

2. **Verify backend running**:
   ```bash
   curl http://localhost:3000/api/health
   # Should return: {"status": "ok"}
   ```

3. **Check port not in use**:
   ```bash
   # Linux/Mac
   lsof -i :3000

   # Windows
   netstat -ano | findstr :3000
   ```

4. **If port in use, change port**:
   ```bash
   export ATG_PORT=3001
   atg-ui
   ```

---

#### Issue: CORS Errors in Browser Console

**Symptoms**:
- Browser console shows CORS errors
- API calls blocked by browser

**Cause**: Frontend and backend on different origins.

**Solution**:

1. **Check origin configuration**:
   - Frontend: `http://localhost:3000`
   - Backend API: Should also be `http://localhost:3000`

2. **Ensure both served from same origin**:
   - Electron app serves both frontend and API on same port
   - No CORS issues expected

3. **If using separate servers** (development):
   ```javascript
   // Backend: Enable CORS
   app.use(cors({
     origin: 'http://localhost:3001',
     credentials: true
   }));
   ```

---

## Error Messages Reference

### Backend Error Messages

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Invalid tenant type` | tenantType not "source" or "gameboard" | Use correct tenant type |
| `Device code not found` | Invalid or expired device code | Get new device code |
| `Token expired` | Access token expired | Refresh or re-authenticate |
| `Not authenticated` | No tokens stored | Sign in |
| `Token tenant mismatch` | Token for wrong tenant | Sign out and sign in to correct tenant |
| `Azure API error` | Microsoft API unavailable | Check connectivity, try again |
| `CSRF token invalid` | Missing or wrong CSRF token | Refresh page to get new CSRF token |

### Azure AD Error Messages

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `authorization_pending` | User hasn't completed auth in browser | Complete authentication in browser |
| `authorization_declined` | User denied consent | Accept consent screen during authentication |
| `expired_token` | Device code expired (15 min) | Get new device code |
| `invalid_grant` | Token revoked or invalid | Re-authenticate |
| `invalid_client` | Client ID configuration error | Contact administrator |
| `access_denied` | Conditional Access policy blocked | Check Conditional Access policies in Azure AD |

---

## Advanced Troubleshooting

### Enable Debug Logging

**Backend Debug Logs**:

```bash
# Enable verbose logging
export ATG_LOG_LEVEL=debug
atg-ui
```

**Frontend Debug Logs**:

```javascript
// Open browser console (F12)
// Enable verbose logging
localStorage.setItem('debug', 'atg:*');

// Reload page
location.reload();
```

### Inspect Token Contents (Debugging Only)

**WARNING**: Only for debugging. Never log tokens in production.

```bash
# Get token
TOKEN=$(curl -s 'http://localhost:3000/api/auth/token?tenantType=source' | jq -r .token)

# Decode JWT (without verification)
echo $TOKEN | cut -d. -f2 | base64 -d | jq .

# Output shows:
# {
#   "aud": "https://management.azure.com",
#   "iss": "https://sts.windows.net/...",
#   "iat": 1706544000,
#   "exp": 1706547600,
#   "tid": "12345678-abcd-...",
#   "upn": "user@tenant.com",
#   ...
# }
```

**Key Fields**:
- `exp`: Expiration timestamp (Unix epoch)
- `tid`: Tenant ID
- `upn`: User principal name
- `aud`: Audience (should be Azure Management API)

### Check Token Storage

**Linux/Mac**:
```bash
# Check storage location
ls -la ~/.config/azuretg/

# Storage is encrypted, but can verify files exist
ls -la ~/.config/azuretg/storage/
```

**Windows**:
```powershell
# Check storage location
dir $env:APPDATA\azuretg\storage
```

**Expected Files**:
```
atg_source_access_token.enc
atg_source_refresh_token.enc
atg_source_expires_at
atg_gameboard_access_token.enc
atg_gameboard_refresh_token.enc
atg_gameboard_expires_at
```

### Capture Network Traffic

**Using Browser DevTools**:

1. Open DevTools (F12)
2. Go to Network tab
3. Filter by "api/auth"
4. Perform authentication
5. Review requests/responses

**Expected Flow**:
```
POST /api/device-code/start → 200 OK (device code)
GET  /api/device-code/status → 200 OK (status: pending)
GET  /api/device-code/status → 200 OK (status: pending)
...
GET  /api/device-code/status → 200 OK (status: completed)
```

---

## Getting Help

### Before Asking for Help

Gather this information:

1. **Error messages** (exact text)
2. **Authentication status**:
   ```bash
   atg auth status --all
   ```
3. **Backend logs** (last 50 lines):
   ```bash
   tail -n 50 ~/.config/azuretg/logs/auth.log
   ```
4. **Browser console errors** (screenshot)
5. **Steps to reproduce**

### Support Channels

- **GitHub Issues**: https://github.com/org/azure-tenant-grapher/issues
- **Documentation**: https://docs.azuretg.example.com
- **Community Forum**: https://community.azuretg.example.com
- **Email Support**: support@azuretg.example.com

### Security Issues

**Do NOT post security issues publicly**. Report via:

- **GitHub Security Advisories** (private disclosure)
- **Email**: security@azuretg.example.com

---

## Related Documentation

- [User Guide](./USER_GUIDE.md) - Step-by-step authentication instructions
- [Architecture Documentation](./ARCHITECTURE.md) - System design details
- [API Reference](./API_REFERENCE.md) - API error codes and responses
- [Security Guide](./SECURITY.md) - Security features and best practices
- [Developer Guide](./DEVELOPER_GUIDE.md) - Integration guide for developers
