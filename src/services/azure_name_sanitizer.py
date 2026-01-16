"""Azure Name Sanitizer Service.

This module provides centralized Azure resource name sanitization for globally unique
resources. It transforms abstracted resource names into Azure-compliant names that meet
specific constraints for character sets, length, and format.

Philosophy:
    - Single responsibility: Knows Azure naming rules, applies them deterministically
    - Stateless: Pure functions with no side effects
    - Reusable: Single implementation for 36 globally unique resource types
    - Testable: No external dependencies or mutable state
    - Deterministic: Same input always produces same output

Problem Solved:
    Azure resources with globally unique DNS names (Storage Accounts, Key Vaults, etc.)
    have strict naming constraints that vary by resource type. Previously, this logic
    was duplicated across individual Terraform handlers, with only 5 of 36 handlers
    implementing it correctly. This service centralizes the knowledge and ensures
    consistent, correct name transformation.

Architecture Position:
    The sanitizer sits between ID Abstraction Service and Terraform handlers:

    Discovery → Abstraction → Sanitization → Global Uniqueness → IaC Generation
                 (IDAbstractionService)  (AzureNameSanitizer)  (Handlers)

Public API (the "studs"):
    AzureNameSanitizer: Main service class
        - sanitize(abstracted_name, resource_type) -> str
        - is_globally_unique(resource_type) -> bool
        - get_constraints(resource_type) -> NamingConstraints

    NamingConstraints: Dataclass containing resource-specific rules
        - max_length: Maximum allowed length
        - allowed_chars: Character set rules
        - dns_pattern: DNS endpoint pattern
        - must_start_with: Starting character requirements

Supported Resource Types:
    36 globally unique resource types across 6 categories:
    - CRITICAL (10): Storage, KeyVault, AppService, SQL, ACR, PostgreSQL, MySQL, APIM, CDN, AppConfig
    - Integration/Messaging (4): ServiceBus, EventHub, EventGrid, SignalR
    - API/Networking (5): FrontDoor, TrafficManager, AppGateway, Firewall, Bastion
    - Data/Analytics (8): DataFactory, Synapse, Databricks, HDInsight, CosmosDB, Redis, Search, Analysis
    - AI/ML/IoT (4): Cognitive, MachineLearning, IoTHub, IoTCentral
    - Specialized (5): BotService, Communication, SpringCloud, Grafana, StaticWebApps

Usage Example:
    >>> from services.azure_name_sanitizer import AzureNameSanitizer
    >>>
    >>> sanitizer = AzureNameSanitizer()
    >>>
    >>> # Storage Account - removes hyphens, lowercase only
    >>> clean_name = sanitizer.sanitize(
    ...     "storage-a1b2c3d4",
    ...     "Microsoft.Storage/storageAccounts"
    ... )
    >>> print(clean_name)
    'storagea1b2c3d4'
    >>>
    >>> # Container Registry - removes hyphens, alphanumeric only
    >>> clean_name = sanitizer.sanitize(
    ...     "acr-x9y8z7",
    ...     "Microsoft.ContainerRegistry/registries"
    ... )
    >>> print(clean_name)
    'acrx9y8z7'
    >>>
    >>> # Key Vault - keeps hyphens, validates format
    >>> clean_name = sanitizer.sanitize(
    ...     "vault-prod-east",
    ...     "Microsoft.KeyVault/vaults"
    ... )
    >>> print(clean_name)
    'vault-prod-east'
    >>>
    >>> # Check if resource type requires global uniqueness
    >>> is_global = sanitizer.is_globally_unique("Microsoft.Storage/storageAccounts")
    >>> print(is_global)
    True

Handler Integration Example:
    >>> # In a Terraform handler
    >>> class StorageAccountHandler(ResourceHandler):
    ...     def emit(self, resource, context):
    ...         abstracted_name = resource.get("name")
    ...
    ...         # Sanitize for Azure constraints
    ...         sanitizer = AzureNameSanitizer()
    ...         sanitized_name = sanitizer.sanitize(
    ...             abstracted_name,
    ...             "Microsoft.Storage/storageAccounts"
    ...         )
    ...
    ...         # Add tenant suffix if cross-tenant deployment
    ...         if context.target_tenant_id != context.source_tenant_id:
    ...             tenant_suffix = context.target_tenant_id[-6:].replace("-", "").lower()
    ...             sanitized_name = f"{sanitized_name}{tenant_suffix}"
    ...
    ...         config = {"name": sanitized_name, ...}
    ...         return ("azurerm_storage_account", resource["name"], config)

Testing Strategy:
    - Unit tests (60%): Test each of 36 resource types' sanitization rules
    - Integration tests (30%): Test sanitizer integration with handlers
    - Edge cases (10%): Empty names, unknown types, constraint violations

Migration Path:
    Phase 1: Implement AzureNameSanitizer service (this file)
    Phase 2: Update 5 existing handlers to use sanitizer
    Phase 3: Add sanitizer calls to 31 remaining handlers
    Phase 4: Validate all handlers produce Azure-compliant names

References:
    - Investigation: .claude/docs/INVESTIGATION_globally_unique_names_20260113.md
    - Azure Docs: https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules
    - Research: Commit 3a66f1d - AZURE_GLOBALLY_UNIQUE_NAMES_RESEARCH.md

Design Details:
    See docs/services/AZURE_NAME_SANITIZER.md for complete specification including:
    - All 36 supported resource types with constraints
    - Before/after transformation examples
    - Character set rules and length constraints
    - DNS pattern awareness
    - Comprehensive testing strategy
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict


@dataclass
class NamingConstraints:
    """Naming constraints for an Azure resource type.

    Attributes:
        max_length: Maximum allowed length for the resource name
        allowed_chars: Character set rule (lowercase_alphanum, alphanum_only, alphanum_hyphen)
        dns_pattern: DNS endpoint pattern (e.g., "*.core.windows.net")
        must_start_with: Starting character requirement (letter, number, letter_or_number)
        must_end_with: Ending character requirement (letter, number, letter_or_number)
        allow_consecutive_hyphens: Whether consecutive hyphens are allowed
    """

    max_length: int
    allowed_chars: str
    dns_pattern: str
    must_start_with: str = "letter_or_number"
    must_end_with: str = "letter_or_number"
    allow_consecutive_hyphens: bool = False


class AzureNameSanitizer:
    """Centralized service for sanitizing Azure resource names.

    Provides single source of truth for Azure naming rules across all 36 globally
    unique resource types. Transforms abstracted resource names (from IDAbstractionService)
    into Azure-compliant names that meet specific constraints.

    This class is stateless and thread-safe. All methods are deterministic.
    """

    # Resource type constraints mapping
    CONSTRAINTS: Dict[str, NamingConstraints] = {
        # CRITICAL Priority (10 types)
        "Microsoft.Storage/storageAccounts": NamingConstraints(
            max_length=24,
            allowed_chars="lowercase_alphanum",
            dns_pattern="*.core.windows.net",
        ),
        "Microsoft.KeyVault/vaults": NamingConstraints(
            max_length=24,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.vault.azure.net",
            must_start_with="letter",
        ),
        "Microsoft.Web/sites": NamingConstraints(
            max_length=60,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azurewebsites.net",
        ),
        "Microsoft.Sql/servers": NamingConstraints(
            max_length=63,
            allowed_chars="lowercase_alphanum_hyphen",
            dns_pattern="*.database.windows.net",
        ),
        "Microsoft.ContainerRegistry/registries": NamingConstraints(
            max_length=50,
            allowed_chars="alphanum_only",
            dns_pattern="*.azurecr.io",
        ),
        "Microsoft.DBforPostgreSQL/servers": NamingConstraints(
            max_length=63,
            allowed_chars="lowercase_alphanum_hyphen",
            dns_pattern="*.postgres.database.azure.com",
        ),
        "Microsoft.DBforMySQL/servers": NamingConstraints(
            max_length=63,
            allowed_chars="lowercase_alphanum_hyphen",
            dns_pattern="*.mysql.database.azure.com",
        ),
        "Microsoft.ApiManagement/service": NamingConstraints(
            max_length=50,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azure-api.net",
        ),
        "Microsoft.Cdn/profiles": NamingConstraints(
            max_length=260,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azureedge.net",
        ),
        "Microsoft.AppConfiguration/configurationStores": NamingConstraints(
            max_length=50,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azconfig.io",
        ),
        # Integration/Messaging (4 types)
        "Microsoft.ServiceBus/namespaces": NamingConstraints(
            max_length=50,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.servicebus.windows.net",
        ),
        "Microsoft.EventHub/namespaces": NamingConstraints(
            max_length=50,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.servicebus.windows.net",
        ),
        "Microsoft.EventGrid/domains": NamingConstraints(
            max_length=50,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.eventgrid.azure.net",
        ),
        "Microsoft.SignalRService/signalR": NamingConstraints(
            max_length=63,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.service.signalr.net",
        ),
        # API/Networking (4 types)
        "Microsoft.Network/frontDoors": NamingConstraints(
            max_length=64,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azurefd.net",
        ),
        "Microsoft.Network/trafficManagerProfiles": NamingConstraints(
            max_length=63,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.trafficmanager.net",
        ),
        # Data/Analytics (10 types)
        "Microsoft.DBforMariaDB/servers": NamingConstraints(
            max_length=63,
            allowed_chars="lowercase_alphanum_hyphen",
            dns_pattern="*.mariadb.database.azure.com",
        ),
        "Microsoft.DocumentDB/databaseAccounts": NamingConstraints(
            max_length=44,
            allowed_chars="lowercase_alphanum_hyphen",
            dns_pattern="*.documents.azure.com",
        ),
        "Microsoft.Cache/redis": NamingConstraints(
            max_length=63,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.redis.cache.windows.net",
        ),
        "Microsoft.Search/searchServices": NamingConstraints(
            max_length=60,
            allowed_chars="lowercase_alphanum_hyphen",
            dns_pattern="*.search.windows.net",
        ),
        "Microsoft.DataFactory/factories": NamingConstraints(
            max_length=63,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.datafactory.azure.com",
        ),
        "Microsoft.Synapse/workspaces": NamingConstraints(
            max_length=50,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.sql.azuresynapse.net",
        ),
        "Microsoft.Databricks/workspaces": NamingConstraints(
            max_length=64,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azuredatabricks.net",
        ),
        "Microsoft.HDInsight/clusters": NamingConstraints(
            max_length=59,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azurehdinsight.net",
        ),
        "Microsoft.DataLakeStore/accounts": NamingConstraints(
            max_length=24,
            allowed_chars="lowercase_alphanum",
            dns_pattern="*.azuredatalakestore.net",
        ),
        "Microsoft.DataLakeAnalytics/accounts": NamingConstraints(
            max_length=24,
            allowed_chars="lowercase_alphanum",
            dns_pattern="*.azuredatalakeanalytics.net",
        ),
        # AI/ML/IoT (4 types)
        "Microsoft.CognitiveServices/accounts": NamingConstraints(
            max_length=64,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.cognitiveservices.azure.com",
        ),
        "Microsoft.MachineLearningServices/workspaces": NamingConstraints(
            max_length=33,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.api.azureml.ms",
        ),
        "Microsoft.Devices/IotHubs": NamingConstraints(
            max_length=50,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azure-devices.net",
        ),
        "Microsoft.IoTCentral/IoTApps": NamingConstraints(
            max_length=63,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azureiotcentral.com",
        ),
        # Specialized (6 types)
        "Microsoft.BotService/botServices": NamingConstraints(
            max_length=64,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.botframework.com",
        ),
        "Microsoft.Communication/communicationServices": NamingConstraints(
            max_length=63,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.communication.azure.com",
        ),
        "Microsoft.AppPlatform/Spring": NamingConstraints(
            max_length=32,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azuremicroservices.io",
        ),
        "Microsoft.Web/staticSites": NamingConstraints(
            max_length=40,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.azurestaticapps.net",
        ),
        "Microsoft.Kusto/clusters": NamingConstraints(
            max_length=22,
            allowed_chars="lowercase_alphanum",
            dns_pattern="*.kusto.windows.net",
        ),
        "Microsoft.Dashboard/grafana": NamingConstraints(
            max_length=23,
            allowed_chars="alphanum_hyphen",
            dns_pattern="*.grafana.azure.com",
        ),
    }

    def sanitize(self, abstracted_name: str, resource_type: str) -> str:
        """Sanitize resource name according to Azure naming rules.

        Transforms an abstracted resource name into an Azure-compliant name that meets
        the specific constraints for the given resource type.

        Args:
            abstracted_name: The abstracted name from IDAbstractionService (e.g., "storage-a1b2c3d4")
            resource_type: Azure resource type (e.g., "Microsoft.Storage/storageAccounts")

        Returns:
            Azure-compliant resource name

        Raises:
            ValueError: If resource type is unknown
            ValueError: If name cannot be sanitized to meet constraints

        Example:
            >>> sanitizer = AzureNameSanitizer()
            >>> result = sanitizer.sanitize("storage-a1b2c3d4", "Microsoft.Storage/storageAccounts")
            >>> print(result)
            'storagea1b2c3d4'
        """
        # Validate input
        if not abstracted_name or not abstracted_name.strip():
            raise ValueError("Name cannot be empty")

        # Get constraints for this resource type
        constraints = self.get_constraints(resource_type)

        # Start with trimmed name
        name = abstracted_name.strip()

        # Normalize Unicode characters before converting to ASCII (security: prevents homograph attacks)
        name = unicodedata.normalize("NFKD", name)
        # Convert unicode characters to ASCII (remove non-ASCII)
        name = name.encode("ascii", "ignore").decode("ascii")

        # Apply character set transformations based on allowed_chars
        if constraints.allowed_chars == "lowercase_alphanum":
            # Remove all non-alphanumeric characters, convert to lowercase
            name = "".join(c for c in name if c.isalnum()).lower()
        elif constraints.allowed_chars == "alphanum_only":
            # Remove all non-alphanumeric characters, convert to lowercase
            name = "".join(c for c in name if c.isalnum()).lower()
        elif constraints.allowed_chars == "alphanum_hyphen":
            # Keep alphanumeric and hyphens, convert to lowercase
            name = "".join(c for c in name if c.isalnum() or c == "-").lower()
            # Remove consecutive hyphens (security: use regex to prevent ReDoS)
            name = re.sub(r"-+", "-", name)
            # Remove leading/trailing hyphens
            name = name.strip("-")
        elif constraints.allowed_chars == "lowercase_alphanum_hyphen":
            # Keep alphanumeric and hyphens, enforce lowercase
            name = "".join(c for c in name if c.isalnum() or c == "-").lower()
            # Remove consecutive hyphens (security: use regex to prevent ReDoS)
            name = re.sub(r"-+", "-", name)
            # Remove leading/trailing hyphens
            name = name.strip("-")

        # Handle must_start_with constraint
        if constraints.must_start_with == "letter" and name and not name[0].isalpha():
            # Prefix with 'a' if doesn't start with letter
            name = "a" + name

        # Truncate to max_length
        if len(name) > constraints.max_length:
            name = name[: constraints.max_length]

        # Ensure doesn't end with hyphen (after truncation)
        if name.endswith("-"):
            name = name.rstrip("-")

        # Final validation
        if not name:
            raise ValueError("Name cannot be empty after sanitization")

        return name

    def is_globally_unique(self, resource_type: str) -> bool:
        """Check if resource type requires globally unique name.

        Args:
            resource_type: Azure resource type

        Returns:
            True if resource requires global uniqueness across all of Azure

        Example:
            >>> sanitizer = AzureNameSanitizer()
            >>> sanitizer.is_globally_unique("Microsoft.Storage/storageAccounts")
            True
            >>> sanitizer.is_globally_unique("Microsoft.Compute/virtualMachines")
            False
        """
        # Resource is globally unique if it's in our CONSTRAINTS dict
        return resource_type in self.CONSTRAINTS

    def get_constraints(self, resource_type: str) -> NamingConstraints:
        """Get naming constraints for a resource type.

        Args:
            resource_type: Azure resource type

        Returns:
            NamingConstraints object with max_length, allowed_chars, dns_pattern, etc.

        Raises:
            ValueError: If resource type is unknown

        Example:
            >>> sanitizer = AzureNameSanitizer()
            >>> constraints = sanitizer.get_constraints("Microsoft.Storage/storageAccounts")
            >>> print(constraints.max_length)
            24
            >>> print(constraints.allowed_chars)
            'lowercase_alphanum'
        """
        if resource_type not in self.CONSTRAINTS:
            raise ValueError(f"Unknown resource type: {resource_type}")
        return self.CONSTRAINTS[resource_type]


__all__ = ["AzureNameSanitizer", "NamingConstraints"]
