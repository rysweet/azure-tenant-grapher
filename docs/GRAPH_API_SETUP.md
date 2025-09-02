# Microsoft Graph API Setup Guide

## Overview

Azure Tenant Grapher uses the Microsoft Graph API to discover Azure AD (Entra ID) users, groups, service principals, and their relationships. This enriches the graph with identity information that complements the Azure Resource Manager data.

## Current Status: ❌ Permissions Not Configured

The Graph API integration is currently **not working** because the required permissions have not been granted to the service principal.

## Required Permissions

The service principal needs the following **Application permissions** (not delegated):

### Minimum Required Permissions
- `User.Read.All` - Read all users' full profiles
- `Group.Read.All` - Read all groups

### Alternative: Single Broad Permission
- `Directory.Read.All` - Read directory data (covers users, groups, service principals, and roles)

### Optional Additional Permissions
- `Application.Read.All` - Read all applications and service principals
- `RoleManagement.Read.Directory` - Read directory role assignments

## Setup Instructions

### Step 1: Navigate to App Registration

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Find your application:
   - Client ID: `c331f235-8306-4227-aef1-9d7e79d11c2b`
   - Or search by name

### Step 2: Add API Permissions

1. Click on your app registration
2. Go to **API permissions** in the left menu
3. Click **Add a permission**
4. Select **Microsoft Graph**
5. Choose **Application permissions** (NOT Delegated permissions)
6. Search for and add:
   - `User.Read.All`
   - `Group.Read.All`
   - OR just add `Directory.Read.All` for broader coverage
7. Click **Add permissions**

### Step 3: Grant Admin Consent

⚠️ **This step requires Azure AD admin privileges**

1. After adding permissions, you'll see them listed with a status
2. Click the **Grant admin consent for [Your Tenant]** button
3. Confirm the consent dialog
4. The Status column should now show green checkmarks

### Step 4: Verify Permissions

Run the included test script to verify permissions are working:

```bash
uv run python test_graph_api.py
```

You should see output like:
```
✅ Can read users (found X on first page)
✅ Can read groups (found Y on first page)
```

## What Gets Discovered

Once permissions are configured, the build process will:

1. **Discover Users**
   - User ID
   - Display name
   - User principal name (email)
   - Mail address

2. **Discover Groups**
   - Group ID
   - Display name
   - Mail address
   - Description

3. **Discover Memberships**
   - User-to-Group relationships
   - Group-to-Group relationships (nested groups)

4. **Create Graph Nodes**
   - `User` nodes for each user
   - `IdentityGroup` nodes for each group
   - `MEMBER_OF` relationships

## Integration with Build Process

The Graph API discovery is automatically included in the build process when:

1. The required environment variables are set:
   - `AZURE_CLIENT_ID`
   - `AZURE_CLIENT_SECRET`
   - `AZURE_TENANT_ID`

2. Graph API permissions are granted (as described above)

3. AAD import is enabled (default):
   - Set `ENABLE_AAD_IMPORT=false` to disable

## Troubleshooting

### Error: "Insufficient privileges to complete the operation"
- **Cause**: Permissions not granted or admin consent not given
- **Solution**: Follow setup instructions above

### Error: "Missing one or more required Azure AD credentials"
- **Cause**: Environment variables not set
- **Solution**: Check your `.env` file has all required variables

### No users/groups discovered
- **Cause**: Empty tenant or permissions issue
- **Solution**: Run `test_graph_api.py` to diagnose

### Rate limiting errors
- **Cause**: Too many requests to Graph API
- **Solution**: The service automatically retries with backoff

## Security Considerations

- Use Application permissions (not Delegated) for service principal access
- Grant only the minimum required permissions
- Rotate client secrets regularly
- Store credentials securely (never commit to git)
- Consider using Managed Identity in production Azure environments

## CLI Commands

### Check Graph API Permissions
```bash
atg check-permissions
```

### Test Graph API Connectivity
```bash
uv run python test_graph_api.py
```

### Build with AAD Discovery
```bash
atg build --tenant-id YOUR_TENANT_ID  # AAD import enabled by default
```

### Build without AAD Discovery
```bash
ENABLE_AAD_IMPORT=false atg build --tenant-id YOUR_TENANT_ID
```

## Impact on Threat Modeling

Having identity information in the graph enables better threat modeling:

- Identifies over-privileged users and groups
- Detects service principals with excessive permissions
- Maps identity-based attack paths
- Highlights accounts without MFA
- Finds stale or unused identities

Without Graph API permissions, these identity-based threats cannot be detected.