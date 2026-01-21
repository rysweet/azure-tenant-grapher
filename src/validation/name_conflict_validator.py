"""Name conflict validation for Azure resource deployment.

This module validates Azure resource names against:
1. Existing resources in the target subscription
2. Globally unique name requirements (36 resource types across all Azure)
3. Azure naming rules and conventions
4. Soft-deleted resources that would block deployment

Auto-fix mode appends naming_suffix to conflicting names or applies custom patterns.

Addresses GAP-014: Global Resource Name Conflict Detection (Issue #312)
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from azure.core.exceptions import (  # type: ignore[import-untyped]
    AzureError,
    ResourceNotFoundError,
)
from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
from azure.mgmt.keyvault import KeyVaultManagementClient  # type: ignore[import-untyped]
from azure.mgmt.resource import ResourceManagementClient  # type: ignore[import-untyped]
from azure.mgmt.storage import StorageManagementClient  # type: ignore[import-untyped]
from azure.mgmt.storage.models import (
    StorageAccountCheckNameAvailabilityParameters,  # type: ignore[import-untyped]
)

logger = logging.getLogger(__name__)


# Azure globally unique resource types
# These resource types have DNS-based public endpoints and require globally unique names
# across ALL Azure subscriptions worldwide. Based on research from commit 3a66f1d.
GLOBALLY_UNIQUE_TYPES = {
    # CRITICAL Priority (10 types) - Common in deployments
    "Microsoft.Storage/storageAccounts",
    "Microsoft.KeyVault/vaults",
    "Microsoft.Web/sites",  # App Services
    "Microsoft.Sql/servers",
    "Microsoft.ContainerRegistry/registries",
    "Microsoft.DBforPostgreSQL/servers",
    "Microsoft.DBforMySQL/servers",
    "Microsoft.DBforMariaDB/servers",
    "Microsoft.Cache/redis",  # Redis Cache
    "Microsoft.DocumentDB/databaseAccounts",  # Cosmos DB
    # Integration/Messaging (4 types)
    "Microsoft.ServiceBus/namespaces",
    "Microsoft.EventHub/namespaces",
    "Microsoft.EventGrid/domains",
    "Microsoft.SignalRService/signalR",
    # API/Networking (5 types)
    "Microsoft.ApiManagement/service",
    "Microsoft.Cdn/profiles",
    "Microsoft.Network/frontDoors",
    "Microsoft.Network/trafficManagerProfiles",
    "Microsoft.AppConfiguration/configurationStores",
    # Data/Analytics (8 types)
    "Microsoft.DataFactory/factories",
    "Microsoft.Synapse/workspaces",
    "Microsoft.Databricks/workspaces",
    "Microsoft.HDInsight/clusters",
    "Microsoft.Search/searchServices",
    "Microsoft.DataLakeStore/accounts",
    "Microsoft.DataLakeAnalytics/accounts",
    "Microsoft.Kusto/clusters",
    # AI/ML/IoT (4 types)
    "Microsoft.CognitiveServices/accounts",
    "Microsoft.MachineLearningServices/workspaces",
    "Microsoft.Devices/IotHubs",
    "Microsoft.IoTCentral/IoTApps",
    # Specialized (5 types)
    "Microsoft.BotService/botServices",
    "Microsoft.Communication/communicationServices",
    "Microsoft.LoadTestService/loadTests",
    "Microsoft.AppPlatform/Spring",  # Spring Cloud
    "Microsoft.Web/staticSites",  # Static Web Apps
}

# Azure naming rules (simplified - covers most common cases)
# Based on official Azure naming conventions and research from commit 3a66f1d
NAMING_RULES = {
    # Storage and Data
    "Microsoft.Storage/storageAccounts": {
        "pattern": r"^[a-z0-9]{3,24}$",
        "description": "3-24 lowercase letters and numbers (no hyphens)",
        "max_length": 24,
    },
    "Microsoft.DocumentDB/databaseAccounts": {
        "pattern": r"^[a-z0-9][a-z0-9-]{1,42}[a-z0-9]$",
        "description": "3-44 lowercase alphanumeric and hyphens",
        "max_length": 44,
    },
    # Security
    "Microsoft.KeyVault/vaults": {
        "pattern": r"^[a-zA-Z][a-zA-Z0-9-]{1,22}[a-zA-Z0-9]$",
        "description": "3-24 alphanumeric and hyphens, start with letter",
        "max_length": 24,
    },
    # Web and App Services
    "Microsoft.Web/sites": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,58}[a-zA-Z0-9]$",
        "description": "2-60 alphanumeric and hyphens",
        "max_length": 60,
    },
    "Microsoft.Web/staticSites": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,38}[a-zA-Z0-9]$",
        "description": "1-40 alphanumeric and hyphens",
        "max_length": 40,
    },
    # Containers
    "Microsoft.ContainerRegistry/registries": {
        "pattern": r"^[a-zA-Z0-9]{5,50}$",
        "description": "5-50 alphanumeric characters (no hyphens)",
        "max_length": 50,
    },
    # Databases
    "Microsoft.Sql/servers": {
        "pattern": r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$",
        "description": "1-63 lowercase alphanumeric and hyphens",
        "max_length": 63,
    },
    "Microsoft.DBforPostgreSQL/servers": {
        "pattern": r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$",
        "description": "3-63 lowercase alphanumeric and hyphens",
        "max_length": 63,
    },
    "Microsoft.DBforMySQL/servers": {
        "pattern": r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$",
        "description": "3-63 lowercase alphanumeric and hyphens",
        "max_length": 63,
    },
    "Microsoft.DBforMariaDB/servers": {
        "pattern": r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$",
        "description": "3-63 lowercase alphanumeric and hyphens",
        "max_length": 63,
    },
    # Messaging
    "Microsoft.ServiceBus/namespaces": {
        "pattern": r"^[a-zA-Z][a-zA-Z0-9-]{4,48}[a-zA-Z0-9]$",
        "description": "6-50 alphanumeric and hyphens, start with letter",
        "max_length": 50,
    },
    "Microsoft.EventHub/namespaces": {
        "pattern": r"^[a-zA-Z][a-zA-Z0-9-]{4,48}[a-zA-Z0-9]$",
        "description": "6-50 alphanumeric and hyphens, start with letter",
        "max_length": 50,
    },
    "Microsoft.EventGrid/domains": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{1,48}[a-zA-Z0-9]$",
        "description": "3-50 alphanumeric and hyphens",
        "max_length": 50,
    },
    # API and Networking
    "Microsoft.ApiManagement/service": {
        "pattern": r"^[a-zA-Z][a-zA-Z0-9-]{0,48}[a-zA-Z0-9]$",
        "description": "1-50 alphanumeric and hyphens, start with letter",
        "max_length": 50,
    },
    "Microsoft.Network/frontDoors": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{3,62}[a-zA-Z0-9]$",
        "description": "5-64 alphanumeric and hyphens",
        "max_length": 64,
    },
    "Microsoft.Network/trafficManagerProfiles": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]$",
        "description": "1-63 alphanumeric and hyphens",
        "max_length": 63,
    },
    "Microsoft.AppConfiguration/configurationStores": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{3,48}[a-zA-Z0-9]$",
        "description": "5-50 alphanumeric and hyphens",
        "max_length": 50,
    },
    # Cache and Search
    "Microsoft.Cache/redis": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]$",
        "description": "1-63 alphanumeric and hyphens",
        "max_length": 63,
    },
    "Microsoft.Search/searchServices": {
        "pattern": r"^[a-z0-9][a-z0-9-]{0,58}[a-z0-9]$",
        "description": "2-60 lowercase alphanumeric and hyphens",
        "max_length": 60,
    },
    # AI/ML
    "Microsoft.CognitiveServices/accounts": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}[a-zA-Z0-9]$",
        "description": "2-64 alphanumeric and hyphens",
        "max_length": 64,
    },
    "Microsoft.MachineLearningServices/workspaces": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,31}[a-zA-Z0-9]$",
        "description": "3-33 alphanumeric and hyphens",
        "max_length": 33,
    },
    "Microsoft.Devices/IotHubs": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{1,48}[a-zA-Z0-9]$",
        "description": "3-50 alphanumeric and hyphens",
        "max_length": 50,
    },
    # Analytics
    "Microsoft.DataFactory/factories": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]$",
        "description": "3-63 alphanumeric and hyphens",
        "max_length": 63,
    },
    "Microsoft.Synapse/workspaces": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,48}[a-zA-Z0-9]$",
        "description": "1-50 alphanumeric and hyphens",
        "max_length": 50,
    },
    "Microsoft.Databricks/workspaces": {
        "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9-_]{0,28}[a-zA-Z0-9]$",
        "description": "3-30 alphanumeric, hyphens, and underscores",
        "max_length": 30,
    },
}


@dataclass
class NameConflict:
    """Represents a detected name conflict for a resource.

    Attributes:
        resource_type: Azure resource type (e.g., Microsoft.Storage/storageAccounts)
        original_name: The original resource name from source
        suggested_name: Auto-fixed name with suffix (if auto_fix=True)
        conflict_reason: Human-readable explanation of the conflict
        resource_group: Resource group where conflict exists (optional)
        location: Azure region where conflict exists (optional)
    """

    resource_type: str
    original_name: str
    conflict_reason: str
    suggested_name: Optional[str] = None
    resource_group: Optional[str] = None
    location: Optional[str] = None

    def __str__(self) -> str:
        """Human-readable conflict description."""
        suffix = f" -> {self.suggested_name}" if self.suggested_name else ""
        return (
            f"{self.resource_type}: {self.original_name}{suffix} "
            f"({self.conflict_reason})"
        )


@dataclass
class NameValidationResult:
    """Result of name conflict validation.

    Attributes:
        conflicts: List of detected name conflicts
        name_mappings: Dict mapping original names to new names (if auto-fixed)
        warnings: List of warning messages
        resources_checked: Number of resources validated
        conflicts_fixed: Number of conflicts auto-fixed
    """

    conflicts: List[NameConflict] = field(default_factory=list)
    name_mappings: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    resources_checked: int = 0
    conflicts_fixed: int = 0

    @property
    def has_conflicts(self) -> bool:
        """Check if any conflicts were detected."""
        return len(self.conflicts) > 0

    @property
    def has_fixes(self) -> bool:
        """Check if any conflicts were auto-fixed."""
        return len(self.name_mappings) > 0


class NameConflictValidator:
    """Validates Azure resource names for deployment conflicts.

    This validator checks that resource names:
    - Don't conflict with existing resources in target subscription
    - Meet global uniqueness requirements
    - Follow Azure naming conventions
    - Don't conflict with soft-deleted resources

    Auto-fix mode appends naming_suffix to conflicting names.
    """

    def __init__(
        self,
        subscription_id: Optional[str] = None,
        naming_suffix: Optional[str] = None,
        preserve_names: bool = False,
        auto_purge_soft_deleted: bool = False,
        credential: Optional[DefaultAzureCredential] = None,
        custom_naming_pattern: Optional[str] = None,
        use_random_suffix: bool = False,
    ):
        """Initialize name conflict validator.

        Args:
            subscription_id: Target Azure subscription ID (required for conflict checking)
            naming_suffix: Suffix to append when fixing conflicts (default: "-copy")
            preserve_names: If True, don't auto-fix conflicts (just report them)
            auto_purge_soft_deleted: If True, purge soft-deleted resources
            credential: Azure credential (defaults to DefaultAzureCredential)
            custom_naming_pattern: Custom pattern for name generation (e.g., "{name}-{random}")
                Supports placeholders: {name}, {random}, {timestamp}, {suffix}
            use_random_suffix: If True, append random suffix instead of fixed suffix
        """
        self.subscription_id = subscription_id
        self.naming_suffix = naming_suffix or "-copy"
        self.preserve_names = preserve_names
        self.auto_purge_soft_deleted = auto_purge_soft_deleted
        self.credential = credential or (
            DefaultAzureCredential() if subscription_id else None
        )
        self.custom_naming_pattern = custom_naming_pattern
        self.use_random_suffix = use_random_suffix

        # Lazy-initialized clients
        self._resource_client: Optional[ResourceManagementClient] = None
        self._storage_client: Optional[StorageManagementClient] = None
        self._keyvault_client: Optional[KeyVaultManagementClient] = None

        # Cache for existing resources
        self._existing_resources: Optional[Dict[str, set[str]]] = None

    @property
    def resource_client(self) -> Optional[ResourceManagementClient]:
        """Lazy-initialized resource management client."""
        if self._resource_client is None and self.credential and self.subscription_id:
            self._resource_client = ResourceManagementClient(
                self.credential, self.subscription_id
            )
        return self._resource_client

    @property
    def storage_client(self) -> Optional[StorageManagementClient]:
        """Lazy-initialized storage management client."""
        if self._storage_client is None and self.credential and self.subscription_id:
            self._storage_client = StorageManagementClient(
                self.credential, self.subscription_id
            )
        return self._storage_client

    @property
    def keyvault_client(self) -> Optional[KeyVaultManagementClient]:
        """Lazy-initialized key vault management client."""
        if self._keyvault_client is None and self.credential and self.subscription_id:
            self._keyvault_client = KeyVaultManagementClient(
                self.credential, self.subscription_id
            )
        return self._keyvault_client

    def validate_and_fix_terraform(
        self, terraform_config: Dict[str, Any], auto_fix: bool = True
    ) -> Tuple[Dict[str, Any], NameValidationResult]:
        """Validate and optionally fix name conflicts in Terraform configuration.

        Args:
            terraform_config: Terraform configuration dict (from JSON)
            auto_fix: If True, automatically fix conflicts by appending suffix

        Returns:
            Tuple of (updated_config, validation_result)
            - updated_config: Modified config if auto_fix=True, otherwise original
            - validation_result: NameValidationResult with conflicts and mappings
        """
        result = NameValidationResult()

        # If no subscription ID, can only validate naming rules (not conflicts)
        if not self.subscription_id:
            logger.warning(
                "No subscription_id provided - skipping conflict detection. "
                "Only validating naming rules."
            )
            result.warnings.append(
                "Subscription ID not provided - conflict detection skipped"
            )
            return terraform_config, result

        # Extract resources from Terraform config
        resources = self._extract_terraform_resources(terraform_config)
        result.resources_checked = len(resources)

        if not resources:
            logger.info("No resources found in Terraform config")
            return terraform_config, result

        # Run async conflict detection
        try:
            conflicts = asyncio.run(self._detect_conflicts(resources))
            result.conflicts = conflicts
        except Exception as e:
            logger.error(str(f"Error during conflict detection: {e}"))
            result.warnings.append(f"Conflict detection failed: {e!s}")
            return terraform_config, result

        # Auto-fix conflicts if enabled
        if auto_fix and conflicts and not self.preserve_names:
            updated_config = self._apply_fixes(terraform_config, conflicts, result)
            result.conflicts_fixed = len(result.name_mappings)
            return updated_config, result

        return terraform_config, result

    async def _detect_conflicts(
        self, resources: List[Dict[str, Any]]
    ) -> List[NameConflict]:
        """Detect name conflicts for planned resources.

        Args:
            resources: List of resources to validate

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Build index of existing resources
        await self._build_existing_resource_index()

        # Check each resource for conflicts
        for resource in resources:
            rtype = resource.get("type")
            rname = resource.get("name")
            rg = resource.get("resource_group")
            location = resource.get("location")

            if not rtype or not rname:
                continue

            # Check naming rules
            naming_conflict = self._check_naming_rules(rname, rtype)
            if naming_conflict:
                conflicts.append(
                    NameConflict(
                        resource_type=rtype,
                        original_name=rname,
                        conflict_reason=naming_conflict,
                        resource_group=rg,
                        location=location,
                    )
                )
                continue

            # Check for existing resources
            if self._existing_resources and rtype is not None:
                if rtype in self._existing_resources:
                    if rname in self._existing_resources[rtype]:
                        conflicts.append(
                            NameConflict(
                                resource_type=rtype,
                                original_name=rname,
                                conflict_reason="Resource already exists in subscription",
                                resource_group=rg,
                                location=location,
                            )
                        )
                        continue

            # Check global uniqueness for specific resource types
            if rtype in GLOBALLY_UNIQUE_TYPES:
                is_available = await self._check_global_uniqueness(rname, rtype)
                if not is_available:
                    conflicts.append(
                        NameConflict(
                            resource_type=rtype,
                            original_name=rname,
                            conflict_reason="Name not globally unique (already taken)",
                            resource_group=rg,
                            location=location,
                        )
                    )

        # Check for soft-deleted Key Vaults
        soft_deleted_conflicts = await self._check_soft_deleted_key_vaults(resources)
        conflicts.extend(soft_deleted_conflicts)

        return conflicts

    async def _build_existing_resource_index(self) -> None:
        """Build index of existing resources in subscription."""
        if self._existing_resources is not None:
            return  # Already built

        self._existing_resources = {}

        if not self.resource_client:
            logger.warning(
                "Resource client not available - skipping existing resource check"
            )
            return

        try:
            logger.info("Building index of existing resources...")
            for resource in self.resource_client.resources.list():
                rtype = resource.type
                rname = resource.name

                # Skip resources with None type or name
                if rtype is None or rname is None:
                    continue

                if rtype not in self._existing_resources:
                    self._existing_resources[rtype] = set()
                self._existing_resources[rtype].add(rname)

            logger.info(
                f"Indexed {sum(len(v) for v in self._existing_resources.values())} "
                f"existing resources"
            )
        except Exception as e:
            logger.error(str(f"Error building resource index: {e}"))
            self._existing_resources = {}

    def _check_naming_rules(self, name: str, resource_type: str) -> Optional[str]:
        """Check if name follows Azure naming rules for resource type.

        Args:
            name: Resource name to validate
            resource_type: Azure resource type

        Returns:
            Error message if invalid, None if valid
        """
        if resource_type not in NAMING_RULES:
            return None  # No specific rules for this type

        rules = NAMING_RULES[resource_type]
        pattern = str(rules["pattern"])
        description = str(rules["description"])
        max_length = rules.get("max_length")

        if max_length and isinstance(max_length, int) and len(name) > max_length:
            return f"Name exceeds max length of {max_length} characters"

        if not re.match(pattern, name):
            return f"Name doesn't match pattern: {description}"

        return None

    async def _check_global_uniqueness(self, name: str, resource_type: str) -> bool:
        """Check if name is globally unique for resource type.

        Args:
            name: Resource name to check
            resource_type: Azure resource type

        Returns:
            True if available, False if taken
        """
        try:
            # Storage account name availability
            if resource_type == "Microsoft.Storage/storageAccounts":
                if self.storage_client:
                    params = StorageAccountCheckNameAvailabilityParameters(name=name)
                    result = (
                        self.storage_client.storage_accounts.check_name_availability(
                            params
                        )
                    )
                    return (
                        result.name_available
                        if result.name_available is not None
                        else True
                    )
                return True  # Can't check, assume available

            # Key Vault name availability
            elif resource_type == "Microsoft.KeyVault/vaults":
                if self.keyvault_client:
                    # Key Vault doesn't have a direct check API, check via list
                    try:
                        self.keyvault_client.vaults.get(
                            resource_group_name="dummy",  # Will fail but checks name
                            vault_name=name,
                        )
                        return False  # If we get here, it exists
                    except ResourceNotFoundError:
                        return True  # Not found means available
                    except AzureError:
                        return True  # Other errors, assume available
                return True

            # For other globally unique types, assume available if not in index
            return True

        except Exception as e:
            logger.warning(str(f"Could not check global uniqueness for {name}: {e}"))
            return True  # Assume available on error

    async def _check_soft_deleted_key_vaults(
        self, resources: List[Dict[str, Any]]
    ) -> List[NameConflict]:
        """Check for soft-deleted Key Vaults that would block deployment.

        Args:
            resources: List of resources to check

        Returns:
            List of conflicts with soft-deleted vaults
        """
        conflicts = []

        if not self.keyvault_client:
            return conflicts

        # Extract Key Vault names
        vault_names = [
            r["name"] for r in resources if r.get("type") == "Microsoft.KeyVault/vaults"
        ]

        if not vault_names:
            return conflicts

        try:
            logger.info(
                str(f"Checking for soft-deleted Key Vaults ({len(vault_names)})...")
            )

            # List all soft-deleted vaults
            deleted_vaults = {}
            for vault in self.keyvault_client.vaults.list_deleted():
                deleted_vaults[vault.name] = vault

            # Check planned vaults
            for vault_name in vault_names:
                if vault_name in deleted_vaults:
                    vault_info = deleted_vaults[vault_name]
                    purge_date = (
                        str(vault_info.properties.scheduled_purge_date)
                        if vault_info.properties
                        else "unknown"
                    )

                    conflicts.append(
                        NameConflict(
                            resource_type="Microsoft.KeyVault/vaults",
                            original_name=vault_name,
                            conflict_reason=f"Key Vault is soft-deleted (purge: {purge_date})",
                            location=(
                                vault_info.properties.location
                                if vault_info.properties
                                else None
                            ),
                        )
                    )

                    # Auto-purge if enabled
                    if self.auto_purge_soft_deleted:
                        try:
                            logger.info(
                                f"Auto-purging soft-deleted vault: {vault_name}"
                            )
                            self.keyvault_client.vaults.begin_purge_deleted(
                                vault_name=vault_name,
                                location=vault_info.properties.location,
                            )
                        except Exception as e:
                            logger.error(
                                str(f"Failed to purge vault {vault_name}: {e}")
                            )

        except Exception as e:
            logger.error(str(f"Error checking soft-deleted vaults: {e}"))

        return conflicts

    def _extract_terraform_resources(
        self, terraform_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract resources from Terraform configuration.

        Args:
            terraform_config: Terraform config dict from JSON

        Returns:
            List of resource dicts with type, name, resource_group, location
        """
        resources = []

        # Handle both direct resource list and nested structure
        if "resources" in terraform_config:
            resource_list = terraform_config["resources"]
            if isinstance(resource_list, list):
                for resource in resource_list:
                    if isinstance(resource, dict):
                        extracted = self._extract_resource_info(resource)
                        if extracted:
                            resources.append(extracted)
        elif isinstance(terraform_config, list):
            for resource in terraform_config:
                if isinstance(resource, dict):
                    extracted = self._extract_resource_info(resource)
                    if extracted:
                        resources.append(extracted)

        return resources

    def _extract_resource_info(
        self, resource: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract relevant info from a single resource.

        Args:
            resource: Resource dict from Terraform config

        Returns:
            Dict with type, name, resource_group, location or None
        """
        # Handle different Terraform config structures
        rtype = resource.get("type")
        name = resource.get("name")

        # Try to get from properties or values
        if not name:
            values = resource.get("values", {})
            name = values.get("name") or resource.get("resource_name")

        if not rtype or not name:
            return None

        resource_group = None
        location = None

        # Extract from values
        values = resource.get("values", {})
        if values:
            resource_group = values.get("resource_group_name") or values.get(
                "resource_group"
            )
            location = values.get("location")

        # Fallback to top-level properties
        if not resource_group:
            resource_group = resource.get("resource_group")
        if not location:
            location = resource.get("location")

        return {
            "type": rtype,
            "name": name,
            "resource_group": resource_group,
            "location": location,
            "original": resource,
        }

    def _apply_fixes(
        self,
        terraform_config: Dict[str, Any],
        conflicts: List[NameConflict],
        result: NameValidationResult,
    ) -> Dict[str, Any]:
        """Apply name fixes to Terraform configuration.

        Args:
            terraform_config: Original Terraform config
            conflicts: List of conflicts to fix
            result: ValidationResult to update with mappings

        Returns:
            Updated Terraform config with fixed names
        """
        import copy

        updated_config = copy.deepcopy(terraform_config)
        name_mappings = {}

        for conflict in conflicts:
            original_name = conflict.original_name
            suggested_name = self._generate_fixed_name(
                original_name, conflict.resource_type
            )

            # Update conflict with suggested name
            conflict.suggested_name = suggested_name
            name_mappings[original_name] = suggested_name

            # Find and update resource in config
            self._update_resource_name(
                updated_config, conflict.resource_type, original_name, suggested_name
            )

        result.name_mappings = name_mappings
        return updated_config

    def _generate_fixed_name(self, original_name: str, resource_type: str) -> str:
        """Generate fixed name by appending suffix or applying custom pattern.

        Args:
            original_name: Original resource name
            resource_type: Azure resource type

        Returns:
            Fixed name with suffix or custom pattern applied
        """
        import secrets
        from datetime import datetime

        # Get max length for resource type
        max_length: Optional[int] = None
        if resource_type in NAMING_RULES:
            max_length_value = NAMING_RULES[resource_type].get("max_length")
            if isinstance(max_length_value, int):
                max_length = max_length_value

        # Apply custom naming pattern if provided
        if self.custom_naming_pattern:
            # Generate random suffix (6 chars alphanumeric)
            random_suffix = secrets.token_hex(3)  # 6 hex chars
            timestamp = datetime.now().strftime("%Y%m%d")

            # Apply pattern substitutions
            new_name = self.custom_naming_pattern.format(
                name=original_name,
                random=random_suffix,
                timestamp=timestamp,
                suffix=self.naming_suffix.lstrip("-"),
            )
        # Use random suffix if enabled
        elif self.use_random_suffix:
            # Generate 6-character random alphanumeric suffix
            random_suffix = secrets.token_hex(3)
            new_name = f"{original_name}-{random_suffix}"
        # Default: fixed suffix
        else:
            new_name = f"{original_name}{self.naming_suffix}"

        # Truncate if needed
        if max_length and len(new_name) > max_length:
            # Remove enough chars from original name to fit suffix
            if self.custom_naming_pattern or self.use_random_suffix:
                # For random/custom patterns, keep more space for the suffix
                trim_length = max_length - 7  # Reserve 7 chars for suffix
                suffix_part = new_name[trim_length:]
                new_name = f"{original_name[:trim_length]}{suffix_part}"
            else:
                trim_length = max_length - len(self.naming_suffix)
                new_name = f"{original_name[:trim_length]}{self.naming_suffix}"

        # Ensure naming rules are still met (lowercase for storage, etc.)
        if resource_type == "Microsoft.Storage/storageAccounts":
            new_name = new_name.lower().replace("-", "")
        elif resource_type == "Microsoft.ContainerRegistry/registries":
            new_name = new_name.replace("-", "")

        return new_name

    def _update_resource_name(
        self,
        config: Dict[str, Any],
        resource_type: str,
        old_name: str,
        new_name: str,
    ) -> None:
        """Update resource name in Terraform config (modifies in-place).

        Args:
            config: Terraform config dict
            resource_type: Azure resource type
            old_name: Original name to replace
            new_name: New name to use
        """
        resources_list: List[Dict[str, Any]] = []

        if "resources" in config:
            resources_value = config["resources"]
            if isinstance(resources_value, list):
                resources_list = resources_value
        elif isinstance(config, list):
            resources_list = config
        else:
            return

        for resource in resources_list:
            if not isinstance(resource, dict):
                continue

            if resource.get("type") == resource_type:
                # Check if this is the resource to update
                if resource.get("name") == old_name:
                    resource["name"] = new_name

                # Also update in values
                if "values" in resource:
                    values = resource["values"]
                    if isinstance(values, dict) and values.get("name") == old_name:
                        values["name"] = new_name

    def save_name_mappings(
        self,
        name_mappings: Dict[str, str],
        out_dir: Path,
        conflicts: Optional[List[NameConflict]] = None,
    ) -> None:
        """Save name mappings to JSON file with conflict information.

        Args:
            name_mappings: Dict mapping original -> new names
            out_dir: Output directory for mappings file
            conflicts: Optional list of conflicts for additional context
        """
        mappings_file = out_dir / "name_mappings.json"

        # Build enhanced mappings with conflict reasons
        enhanced_mappings = []
        for original, new in name_mappings.items():
            mapping_entry = {
                "original_name": original,
                "new_name": new,
                "reason": "Name conflict detected",
            }

            # Find matching conflict for additional context
            if conflicts:
                for conflict in conflicts:
                    if conflict.original_name == original:
                        mapping_entry["reason"] = conflict.conflict_reason
                        mapping_entry["resource_type"] = conflict.resource_type
                        if conflict.resource_group:
                            mapping_entry["resource_group"] = conflict.resource_group
                        break

            enhanced_mappings.append(mapping_entry)

        output = {
            "description": "Name conflict resolution mappings",
            "naming_suffix": self.naming_suffix,
            "total_conflicts": len(name_mappings),
            "mappings": enhanced_mappings,
        }

        with open(mappings_file, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(str(f"Saved name mappings to {mappings_file}"))
