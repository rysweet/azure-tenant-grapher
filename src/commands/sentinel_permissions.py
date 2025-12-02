"""
Service Principal Permission Management for Sentinel Setup.

This module handles automatic permission checking and granting for the
service principal used by Sentinel automation.

Philosophy:
- Self-provisioning: ATG checks and fixes its own permissions
- Uses az CLI for role assignments (requires user admin auth)
- Service principal does the actual work
"""

import json
import logging
import subprocess
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class SentinelPermissionManager:
    """
    Manage service principal permissions for Sentinel setup.

    Checks if SP has required roles, and uses az CLI to grant them if missing.
    """

    REQUIRED_ROLES = [
        "Contributor",  # For resource creation
        "Microsoft Sentinel Contributor",  # For Sentinel operations
    ]

    def __init__(self, subscription_id: str, sp_object_id: str):
        """
        Initialize permission manager.

        Args:
            subscription_id: Azure subscription ID
            sp_object_id: Service principal object ID (not client ID!)
        """
        self.subscription_id = subscription_id
        self.sp_object_id = sp_object_id

    def check_sp_permissions(self) -> Tuple[bool, List[str]]:
        """
        Check if service principal has all required permissions.

        Returns:
            Tuple of (has_all_permissions, missing_roles)
        """
        logger.info(f"Checking permissions for SP: {self.sp_object_id}")

        try:
            # Query role assignments for the SP
            result = subprocess.run(
                [
                    "az",
                    "role",
                    "assignment",
                    "list",
                    "--assignee",
                    self.sp_object_id,
                    "--subscription",
                    self.subscription_id,
                    "--query",
                    "[].roleDefinitionName",
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )

            assigned_roles = json.loads(result.stdout)
            logger.info(f"SP has roles: {assigned_roles}")

            # Check which required roles are missing
            missing_roles = [
                role for role in self.REQUIRED_ROLES if role not in assigned_roles
            ]

            has_all = len(missing_roles) == 0

            if has_all:
                logger.info("✅ SP has all required permissions")
            else:
                logger.warning(f"⚠️  SP missing roles: {missing_roles}")

            return has_all, missing_roles

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to check SP permissions: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            raise

    def grant_missing_permissions(self, missing_roles: List[str]) -> bool:
        """
        Grant missing permissions to service principal using az CLI.

        This requires the current user (running atg) to have permission to grant roles.

        Args:
            missing_roles: List of role names to grant

        Returns:
            True if all permissions granted successfully
        """
        logger.info(f"Granting {len(missing_roles)} missing roles to SP...")

        all_granted = True

        for role in missing_roles:
            logger.info(f"Granting role: {role}")

            try:
                # Set subscription context first
                subprocess.run(
                    ["az", "account", "set", "--subscription", self.subscription_id],
                    capture_output=True,
                    timeout=30,
                    check=True,
                )

                result = subprocess.run(
                    [
                        "az",
                        "role",
                        "assignment",
                        "create",
                        "--assignee",
                        self.sp_object_id,
                        "--role",
                        role,
                        "--scope",
                        f"/subscriptions/{self.subscription_id}",
                        "--subscription",
                        self.subscription_id,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=True,
                )

                logger.info(f"✅ Granted role: {role}")

            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to grant role {role}: {e.stderr}")
                all_granted = False
            except Exception as e:
                logger.error(f"Error granting role {role}: {e}")
                all_granted = False

        return all_granted

    def ensure_permissions(self) -> bool:
        """
        Ensure service principal has all required permissions.

        Checks current permissions and grants missing ones if needed.

        Returns:
            True if SP has (or was granted) all required permissions
        """
        # Check current permissions
        has_all, missing = self.check_sp_permissions()

        if has_all:
            return True

        # Grant missing permissions
        logger.info(f"SP missing {len(missing)} required roles, attempting to grant...")
        logger.info("Note: This requires current user to have admin permissions")

        granted = self.grant_missing_permissions(missing)

        if not granted:
            logger.error("Failed to grant all required permissions")
            return False

        # Verify permissions were granted
        logger.info("Verifying permissions were granted...")
        has_all_now, still_missing = self.check_sp_permissions()

        if not has_all_now:
            logger.error(f"Permission grant verification failed. Still missing: {still_missing}")
            return False

        logger.info("✅ All required permissions verified")
        return True


def get_sp_object_id_from_client_id(client_id: str) -> Optional[str]:
    """
    Get service principal object ID from client ID using az CLI.

    Args:
        client_id: Application (client) ID

    Returns:
        Object ID of the service principal, or None if not found
    """
    try:
        result = subprocess.run(
            [
                "az",
                "ad",
                "sp",
                "show",
                "--id",
                client_id,
                "--query",
                "id",  # This is the object ID
                "-o",
                "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        object_id = result.stdout.strip()
        logger.info(f"SP object ID for client {client_id[:8]}...: {object_id}")
        return object_id

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get SP object ID: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"Error getting SP object ID: {e}")
        return None
