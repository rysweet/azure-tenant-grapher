#!/usr/bin/env python3
"""
Test Microsoft Graph API connectivity and permissions.
This script helps diagnose issues with AAD/Entra ID user and group discovery.
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_graph_api():
    """Test Microsoft Graph API connectivity and permissions."""
    
    # Check environment variables
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        logger.error("Missing required environment variables:")
        if not tenant_id:
            logger.error("  - AZURE_TENANT_ID")
        if not client_id:
            logger.error("  - AZURE_CLIENT_ID")
        if not client_secret:
            logger.error("  - AZURE_CLIENT_SECRET")
        return False
    
    logger.info(f"Testing Graph API with tenant: {tenant_id}")
    logger.info(f"Using client ID: {client_id}")
    
    try:
        from azure.identity import ClientSecretCredential
        from msgraph import GraphServiceClient
        from msgraph.generated.models.o_data_errors.o_data_error import ODataError
        
        # Create credential
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Test token acquisition
        logger.info("Testing token acquisition...")
        scopes = ['https://graph.microsoft.com/.default']
        token = credential.get_token(*scopes)
        logger.info(f"✅ Successfully acquired token (expires: {token.expires_on})")
        
        # Initialize Graph client
        logger.info("Initializing Graph client...")
        client = GraphServiceClient(credentials=credential, scopes=scopes)
        
        # Test 1: Check if we can read users
        logger.info("\n=== Testing User.Read permissions ===")
        try:
            users_result = await client.users.get()
            if users_result and users_result.value:
                user_count = len(users_result.value)
                logger.info(f"✅ Can read users (found {user_count} on first page)")
                if user_count > 0:
                    first_user = users_result.value[0]
                    logger.info(f"   Sample user: {first_user.display_name} ({first_user.user_principal_name})")
            else:
                logger.warning("⚠️  No users returned (might be empty tenant)")
        except ODataError as e:
            logger.error(f"❌ Cannot read users: {e.error.message if e.error else str(e)}")
            logger.error(f"   Status code: {e.response_status_code}")
            if e.response_status_code == 403:
                logger.error("   Permission needed: User.Read.All or Directory.Read.All")
        
        # Test 2: Check if we can read groups
        logger.info("\n=== Testing Group.Read permissions ===")
        try:
            groups_result = await client.groups.get()
            if groups_result and groups_result.value:
                group_count = len(groups_result.value)
                logger.info(f"✅ Can read groups (found {group_count} on first page)")
                if group_count > 0:
                    first_group = groups_result.value[0]
                    logger.info(f"   Sample group: {first_group.display_name}")
            else:
                logger.warning("⚠️  No groups returned (might be empty tenant)")
        except ODataError as e:
            logger.error(f"❌ Cannot read groups: {e.error.message if e.error else str(e)}")
            logger.error(f"   Status code: {e.response_status_code}")
            if e.response_status_code == 403:
                logger.error("   Permission needed: Group.Read.All or Directory.Read.All")
        
        # Test 3: Check if we can read service principals
        logger.info("\n=== Testing ServicePrincipal.Read permissions ===")
        try:
            sp_result = await client.service_principals.get()
            if sp_result and sp_result.value:
                sp_count = len(sp_result.value)
                logger.info(f"✅ Can read service principals (found {sp_count} on first page)")
                if sp_count > 0:
                    first_sp = sp_result.value[0]
                    logger.info(f"   Sample SP: {first_sp.display_name}")
            else:
                logger.warning("⚠️  No service principals returned")
        except ODataError as e:
            logger.error(f"❌ Cannot read service principals: {e.error.message if e.error else str(e)}")
            logger.error(f"   Status code: {e.response_status_code}")
            if e.response_status_code == 403:
                logger.error("   Permission needed: Application.Read.All or Directory.Read.All")
        
        # Test 4: Check if we can read directory roles
        logger.info("\n=== Testing DirectoryRole.Read permissions ===")
        try:
            roles_result = await client.directory_roles.get()
            if roles_result and roles_result.value:
                role_count = len(roles_result.value)
                logger.info(f"✅ Can read directory roles (found {role_count})")
                if role_count > 0:
                    first_role = roles_result.value[0]
                    logger.info(f"   Sample role: {first_role.display_name}")
            else:
                logger.warning("⚠️  No directory roles returned")
        except ODataError as e:
            logger.error(f"❌ Cannot read directory roles: {e.error.message if e.error else str(e)}")
            logger.error(f"   Status code: {e.response_status_code}")
            if e.response_status_code == 403:
                logger.error("   Permission needed: RoleManagement.Read.Directory or Directory.Read.All")
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("REQUIRED GRAPH API PERMISSIONS:")
        logger.info("  Minimum for user/group discovery:")
        logger.info("    - User.Read.All")
        logger.info("    - Group.Read.All")
        logger.info("  OR grant broader permission:")
        logger.info("    - Directory.Read.All (covers users, groups, service principals, roles)")
        logger.info("\nTo grant permissions:")
        logger.info("  1. Go to Azure Portal > Azure Active Directory > App registrations")
        logger.info(f"  2. Find your app (Client ID: {client_id})")
        logger.info("  3. Go to API permissions > Add a permission > Microsoft Graph > Application permissions")
        logger.info("  4. Add the required permissions listed above")
        logger.info("  5. Click 'Grant admin consent' (requires admin privileges)")
        logger.info("="*60)
        
        return True
        
    except ImportError as e:
        logger.error(f"Missing required Python package: {e}")
        logger.error("Install with: pip install msgraph-sdk azure-identity")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_graph_api())
    sys.exit(0 if success else 1)