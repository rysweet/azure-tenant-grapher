"""Key Vault conflict handler for soft-delete naming conflicts.

This module detects and resolves naming conflicts between desired Key Vault names
and soft-deleted Key Vaults in Azure. Supports both purge (destructive) and
rename (safe) resolution strategies.

Philosophy:
- Ruthless simplicity: Synchronous purge with polling, no async complexity
- Zero-BS: Full implementation, no stubs or placeholders
- Clear contracts: Well-defined inputs, outputs, and side effects
"""

import logging
import re
from typing import Dict, List, Optional, Set

from azure.core.exceptions import HttpResponseError, ServiceRequestError
from azure.identity import DefaultAzureCredential
from azure.mgmt.keyvault import KeyVaultManagementClient

logger = logging.getLogger(__name__)

__all__ = ["KeyVaultHandler"]


class KeyVaultHandler:
    """Handles Key Vault naming conflicts caused by soft-delete.

    When Azure Key Vaults are deleted with soft-delete enabled (default),
    they remain in "soft-deleted" state for 7-90 days. Attempting to create
    a vault with the same name during this period fails.

    This handler:
    1. Queries Azure for soft-deleted vaults in target subscription
    2. Detects naming conflicts with desired vault names
    3. Resolves conflicts via purge (if auto_purge=True) or rename
    4. Returns name mappings for IaC generation

    Side Effects:
        - Makes Azure API calls (list_deleted, begin_purge_deleted_vault)
        - Purges soft-deleted vaults if auto_purge=True (DESTRUCTIVE, irreversible)
        - Blocks up to 60 seconds per purge operation
    """

    def handle_vault_conflicts(
        self,
        vault_names: List[str],
        subscription_id: str,
        location: Optional[str] = None,
        auto_purge: bool = False,
    ) -> Dict[str, str]:
        """Check for Key Vault conflicts and optionally resolve them.

        Args:
            vault_names: List of Key Vault names to check for conflicts
            subscription_id: Azure subscription ID for vault lookup
            location: Optional Azure region filter (e.g., 'eastus').
                     Only soft-deleted vaults in this location considered.
            auto_purge: If True, purge soft-deleted vaults (DESTRUCTIVE).
                       If False, generate unique names for conflicts.

        Returns:
            Dictionary mapping old names to new names for conflicts.
            Empty dict if no conflicts or all conflicts purged.

        Raises:
            ValueError: If vault_names is None or empty
            PermissionError: If insufficient Azure permissions for purge
            TimeoutError: If purge operation exceeds 60-second timeout
            ServiceRequestError: If Azure API fails (network, auth, etc.)

        Examples:
            >>> handler = KeyVaultHandler()
            >>> # No conflicts
            >>> handler.handle_vault_conflicts(
            ...     vault_names=["my-vault"],
            ...     subscription_id="sub-12345"
            ... )
            {}

            >>> # Conflict resolved by renaming
            >>> handler.handle_vault_conflicts(
            ...     vault_names=["my-vault"],
            ...     subscription_id="sub-12345",
            ...     auto_purge=False
            ... )
            {'my-vault': 'my-vault-v2'}

            >>> # Conflict resolved by purge (DESTRUCTIVE)
            >>> handler.handle_vault_conflicts(
            ...     vault_names=["my-vault"],
            ...     subscription_id="sub-12345",
            ...     auto_purge=True
            ... )
            {}  # Original name now available
        """
        # Validate inputs
        if vault_names is None:
            raise ValueError("vault_names cannot be None")
        if not vault_names:
            raise ValueError("vault_names cannot be empty")

        logger.info(
            f"Checking {len(vault_names)} vault names for conflicts "
            f"in subscription {subscription_id}"
        )

        try:
            # Create Azure client (per-call, no persistent client)
            credential = DefaultAzureCredential()
            client = KeyVaultManagementClient(credential, subscription_id)

            # List all soft-deleted vaults in subscription
            logger.debug("Querying Azure for soft-deleted Key Vaults")
            deleted_vaults = list(client.vaults.list_deleted())
            logger.info(f"Found {len(deleted_vaults)} soft-deleted vaults")

            # Filter by location if specified
            if location:
                deleted_vaults = [
                    v
                    for v in deleted_vaults
                    if v.properties.location.lower() == location.lower()
                ]
                logger.debug(
                    f"After location filter ({location}): {len(deleted_vaults)} vaults"
                )

            # Build set of soft-deleted vault names
            deleted_names: Set[str] = {v.name for v in deleted_vaults}

            # Find conflicts (case-sensitive matching per Azure behavior)
            conflicts = [name for name in vault_names if name in deleted_names]

            if not conflicts:
                logger.info("No naming conflicts detected")
                return {}

            logger.warning(f"Detected {len(conflicts)} naming conflicts: {conflicts}")

            # Resolve conflicts
            name_mappings: Dict[str, str] = {}

            if auto_purge:
                # Purge conflicts (DESTRUCTIVE)
                logger.warning(
                    f"auto_purge=True: Purging {len(conflicts)} soft-deleted vaults"
                )
                for conflict_name in conflicts:
                    self._purge_soft_deleted_vault(
                        client=client,
                        vault_name=conflict_name,
                        deleted_vaults=deleted_vaults,
                    )
                # No name mappings needed (original names now available)
            else:
                # Generate unique names for conflicts
                logger.info(
                    f"auto_purge=False: Generating unique names for {len(conflicts)} conflicts"
                )
                for conflict_name in conflicts:
                    new_name = self._generate_unique_name(
                        base_name=conflict_name,
                        existing_names=deleted_names.union(set(vault_names)),
                    )
                    name_mappings[conflict_name] = new_name
                    logger.info(f"Name mapping: {conflict_name} -> {new_name}")

            return name_mappings

        except ServiceRequestError as e:
            logger.error(f"Azure service request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in handle_vault_conflicts: {e}")
            raise

    def _purge_soft_deleted_vault(
        self,
        client: KeyVaultManagementClient,
        vault_name: str,
        deleted_vaults: List,
    ) -> None:
        """Purge a soft-deleted vault and wait for completion.

        Args:
            client: Azure KeyVaultManagementClient
            vault_name: Name of vault to purge
            deleted_vaults: List of deleted vault objects (to find location)

        Raises:
            PermissionError: If insufficient permissions (403 Forbidden)
            TimeoutError: If purge exceeds 60-second timeout
            HttpResponseError: For other Azure API errors
        """
        # Find vault object to get location (required for purge)
        vault = next((v for v in deleted_vaults if v.name == vault_name), None)
        if not vault:
            raise ValueError(f"Vault {vault_name} not found in deleted_vaults list")

        vault_location = vault.properties.location

        logger.info(f"Purging soft-deleted vault: {vault_name} in {vault_location}")

        try:
            # Begin purge operation (async operation)
            poller = client.vaults.begin_purge_deleted_vault(
                vault_name=vault_name,
                location=vault_location,
            )

            # Wait for purge to complete (blocks up to 60 seconds)
            poller.result(timeout=60)

            logger.info(f"Successfully purged vault: {vault_name}")

        except TimeoutError as e:
            error_msg = (
                f"Purge operation timed out (>60s) for vault: {vault_name}. "
                f"Vault may still be purging in Azure. "
                f"Original error: {e}"
            )
            logger.error(error_msg)
            raise TimeoutError(error_msg) from e

        except HttpResponseError as e:
            # Check for permission error (403 Forbidden)
            if e.status_code == 403:
                error_msg = (
                    f"Insufficient permissions to purge vault: {vault_name}. "
                    f"Required: Microsoft.KeyVault/locations/deletedVaults/purge/action. "
                    f"Original error: {e.message}"
                )
                logger.error(error_msg)
                raise PermissionError(error_msg) from e
            else:
                logger.error(f"Azure API error during purge of {vault_name}: {e}")
                raise

    def _generate_unique_name(
        self,
        base_name: str,
        existing_names: Set[str],
    ) -> str:
        """Generate unique vault name by appending version suffix.

        Tries base_name-v2, base_name-v3, etc. until a unique name is found.

        Args:
            base_name: Original vault name
            existing_names: Set of names to avoid (soft-deleted + input names)

        Returns:
            Unique name with -vN suffix

        Examples:
            >>> handler = KeyVaultHandler()
            >>> handler._generate_unique_name("my-vault", {"my-vault"})
            'my-vault-v2'
            >>> handler._generate_unique_name("my-vault", {"my-vault", "my-vault-v2"})
            'my-vault-v3'
        """
        # Check if base_name already has a version suffix
        version_match = re.search(r"-v(\d+)$", base_name)

        if version_match:
            # Extract base without version
            base_without_version = base_name[: version_match.start()]
            start_version = int(version_match.group(1)) + 1
        else:
            base_without_version = base_name
            start_version = 2

        # Try incrementing versions until unique name found
        version = start_version
        while True:
            candidate = f"{base_without_version}-v{version}"
            if candidate not in existing_names:
                return candidate
            version += 1

            # Safety limit to prevent infinite loop
            if version > 100:
                raise ValueError(
                    f"Could not generate unique name for {base_name} after 100 attempts"
                )
