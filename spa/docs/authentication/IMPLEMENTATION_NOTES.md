# Authentication Implementation Notes

## Overview

This document explains the Azure CLI-based authentication implementation for the Auth Tab (Tasks 26 & 27).

## Architecture

### Components

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐      ┌───────────┐
│  Auth Tab   │─────>│ AuthContext  │─────>│ Backend Routes  │─────>│ az login  │
│     UI      │<─────│   (Polling)  │<─────│  (Capture)      │<─────│ subprocess│
└─────────────┘      └──────────────┘      └─────────────────┘      └───────────┘
       │                                              │
       │                                              │
       v                                              v
┌─────────────┐                              ┌─────────────────┐
│   Modal     │                              │ DualAuthService │
│ (Device Code)│                              │  (Token Store)  │
└─────────────┘                              └─────────────────┘
```

## Authentication Flow

### Step 1: User Initiates Sign In
- **File**: `spa/renderer/src/components/tabs/AuthTab.tsx`
- **Function**: `handleSignIn()`
- **Action**: User enters tenant ID and clicks "Sign In"

### Step 2: Trigger az login
- **File**: `spa/renderer/src/context/AuthContext.tsx`
- **Function**: `startDeviceCodeFlow()`
- **API Call**: `POST /api/auth/azure-cli/login`
- **Action**: Backend spawns `az login --tenant <id> --use-device-code`

### Step 3: Capture Device Code
- **File**: `spa/backend/src/routes/auth.routes.ts`
- **Endpoint**: `POST /azure-cli/login`
- **Action**:
  - Spawns az login subprocess
  - Captures stderr output (az login writes to stderr, not stdout!)
  - Parses device code using regex: `/code ([A-Z0-9]+)/i`
  - Parses URL using regex: `/https:\/\/[^\s]+\/device(?:login)?/i`
  - Returns device code info to frontend

### Step 4: Display Device Code
- **File**: `spa/renderer/src/components/AuthLoginModal.tsx`
- **Action**:
  - Shows device code in large text
  - Shows clickable verification URL
  - Shows QR code for mobile authentication
  - Shows countdown timer

### Step 5: User Completes Authentication
- **User Action**:
  - Opens browser to https://microsoft.com/device
  - Enters device code
  - Completes Microsoft authentication (may include MFA)

### Step 6: Poll for Completion
- **File**: `spa/renderer/src/context/AuthContext.tsx`
- **Function**: `useEffect()` polling loop
- **API Call**: `GET /api/auth/azure-cli/status` (every 5 seconds)
- **Action**:
  - Backend attempts to get token using AzureCliCredential
  - If successful, backend validates tenant and stores token
  - Returns 200 (success) or 202 (pending)

### Step 7: Update UI
- **File**: `spa/renderer/src/context/AuthContext.tsx`
- **Action**:
  - Receives success response (200)
  - Updates `sourceAuth` or `targetAuth` state
  - Stops polling
  - Closes modal
- **Result**: UI shows "✅ Authenticated"

### Step 8: Footer Updates (Task 27)
- **File**: `spa/renderer/src/hooks/useTenantName.ts`
- **Action**:
  - Detects `auth.sourceAuth.authenticated === true`
  - Fetches tenant ID from token endpoint
  - Formats tenant ID for display
  - Footer updates to show tenant

## Key Design Decisions

### Why AzureCliCredential instead of DefaultAzureCredential?

**Problem**: DefaultAzureCredential tries multiple sources in this order:
1. Environment variables (service principal)
2. Managed Identity
3. Azure CLI
4. PowerShell
5. VS Code
6. etc.

This caused "ghost logins" where:
- User runs `az logout`
- But PowerShell or VS Code still had cached credentials
- System showed as authenticated to wrong tenant
- Very confusing UX!

**Solution**: Use `AzureCliCredential` directly
- Only uses Azure CLI (explicit, predictable)
- User has full control via `az login` and `az logout`
- No mystery credential sources

### Why spawn instead of exec for az login?

**spawn**:
- Streams output as it arrives (real-time)
- We can capture device code immediately
- Better for long-running processes
- Process continues in background

**exec**:
- Waits for process to complete
- Returns all output at once
- Would block for entire authentication duration
- Not suitable for async flows

### Why capture stderr instead of stdout?

Azure CLI writes:
- **stdout**: JSON results, structured data
- **stderr**: User-facing messages, device codes, warnings

The device code message goes to stderr, so we must listen to stderr!

### Why polling instead of webhooks?

**Polling advantages**:
- Simple to implement and understand
- Works with any firewall/network setup
- No need for public endpoints or tunneling
- Easy to debug (just check poll requests)
- Resilient to network blips (just retries)

**Webhook disadvantages**:
- Requires public endpoint or ngrok-style tunneling
- Firewall/NAT complications
- More moving parts
- Harder to debug

5-second polling is good balance between responsiveness and server load.

## Security Features

### 1. Tenant Validation
- **File**: `spa/backend/src/services/dual-auth.service.ts`
- **Method**: `authenticateWithDefaultCredential()`
- **How**: Decodes JWT token, extracts `tid` claim, compares to requested tenant
- **Why**: Prevents using wrong tenant's tokens (security issue!)

### 2. CSRF Protection
- **Middleware**: `validateCSRF` in auth.routes.ts
- **Applied to**: All POST endpoints (state-changing operations)
- **Why**: Prevents cross-site request forgery attacks

### 3. Rate Limiting
- **Middleware**: `authRateLimiter` in auth.routes.ts
- **Limit**: 10 requests per minute per IP
- **Why**: Prevents brute force attacks and abuse

### 4. Token Storage
- **File**: `spa/backend/src/services/token-storage.service.ts`
- **Security**:
  - Tokens stored in backend (not browser localStorage)
  - Encryption at rest
  - Refresh tokens never exposed to frontend
  - Tokens validated on every use

## Common Issues and Solutions

### Issue: "Failed to capture device code"
**Cause**: Regex didn't match az login output
**Solution**: Check logs for actual output format, update regex
**Logs**: Look for `[AUTH-ROUTE] az login output: ...`

### Issue: "Tenant mismatch" error
**Cause**: Azure CLI logged into different tenant than requested
**Solution**: Run `az login --tenant <correct-tenant-id>`
**Note**: This is intentional security feature, not a bug!

### Issue: Polling never completes
**Cause**: User didn't complete browser authentication, or az login failed
**Solution**:
- Check Logs tab for errors
- Verify user completed device code in browser
- Check if code expired (15 min timeout)

### Issue: Footer shows "Unknown" after authentication
**Cause**: useTenantName hook not checking AuthContext
**Solution**: Already fixed in Task 27
**How**: Hook now checks `auth.sourceAuth.authenticated` first

## Files Modified (Tasks 26 & 27)

### Backend
- `spa/backend/src/routes/auth.routes.ts`
  - Added `/azure-cli/login` endpoint (triggers az login)
  - Added `/azure-cli/status` endpoint (polling)
  - Modified `/token` endpoint (returns tenantId)

- `spa/backend/src/services/dual-auth.service.ts`
  - Added `authenticateWithDefaultCredential()` method
  - Changed from DefaultAzureCredential to AzureCliCredential
  - Added JWT decoding for tenant validation

### Frontend
- `spa/renderer/src/context/AuthContext.tsx`
  - Modified `startDeviceCodeFlow()` to call new endpoint
  - Updated polling to use `/azure-cli/status`
  - Added device code capture and modal display

- `spa/renderer/src/components/tabs/AuthTab.tsx`
  - Updated `handleSignIn()` to open modal with device code
  - Added error display in UI

- `spa/renderer/src/hooks/useTenantName.ts`
  - Added AuthContext as priority source for tenant ID
  - Footer now updates when user authenticates

## Testing

### Test 1: Complete Authentication Flow
1. Go to Auth Tab
2. Enter tenant ID: `3cd87a41-1f61-4aef-a212-cefdecd9a2d1`
3. Click "Sign In"
4. Modal appears with device code
5. Open browser to URL shown
6. Enter code
7. Complete authentication
8. Wait 5-10 seconds
9. UI updates to "✅ Authenticated"
10. Footer shows tenant ID ← Task 27

### Test 2: Wrong Tenant
1. Login to tenant A with az login
2. In Auth Tab, try to authenticate to tenant B
3. Should show error: "Tenant mismatch: logged into A but requested B"

### Test 3: Not Logged In
1. Run `az logout`
2. Clear all caches (see .env file - comment out service principal)
3. Try to Sign In
4. Should show: "Please run 'az login'..." ← But shouldn't happen with new flow!

## Logs to Watch

Enable detailed logging by checking the Logs tab when testing:

```
[AUTH-ROUTE] Starting az login for tenantType=source, tenantId=xxx
[AUTH-ROUTE] Executing: az login --tenant xxx --use-device-code
[AUTH-ROUTE] az login output: To sign in, use a web browser...
[AUTH-ROUTE] ✅ Device code captured: ABC123
[AUTH-ROUTE] ✅ Returning device code to frontend

[AUTH-ROUTE] Checking auth status for source tenant: xxx
[AUTH] Starting authentication for source tenant: xxx
[AUTH] Using AzureCliCredential (ONLY Azure CLI)...
[AUTH] Token received successfully
[AUTH] Token tenant ID: xxx
[AUTH] Requested tenant ID: xxx
[AUTH] ✅ Tenant validation passed
[AUTH] ✅ Successfully authenticated source tenant
```

## Future Improvements

1. **Auto-open browser**: Could use `open` package to automatically open browser to device code URL
2. **Copy button**: Add button to copy device code to clipboard
3. **Multiple simultaneous logins**: Currently only supports one az login at a time
4. **Token refresh UI**: Show when token is being refreshed in background
5. **Logout button**: Add global logout that runs `az logout`

---

**Last Updated**: 2026-01-31 (Tasks 26 & 27)
**Author**: Claude (Pirate Mode 🏴‍☠️)
