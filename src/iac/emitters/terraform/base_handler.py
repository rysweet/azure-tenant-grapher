"""Base handler interface for Azure resource type handlers.

This module defines the abstract base class that all resource handlers
must implement. Each handler is responsible for converting one or more
Azure resource types into Terraform resource configurations.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from .context import EmitterContext

logger = logging.getLogger(__name__)


class ResourceHandler(ABC):
    """Abstract base class for Azure resource type handlers.

    Each handler is responsible for converting one or more Azure resource
    types into Terraform resource configurations.

    Handlers should be:
    - Focused: Handle related resource types only
    - Stateless: Use EmitterContext for shared state
    - Testable: Pure functions where possible
    - Self-documenting: Clear mapping declarations

    Usage:
        @handler
        class StorageAccountHandler(ResourceHandler):
            HANDLED_TYPES = {"Microsoft.Storage/storageAccounts"}
            TERRAFORM_TYPES = {"azurerm_storage_account"}

            def emit(self, resource, context):
                # Convert resource to Terraform config
                return ("azurerm_storage_account", "name", {...})
    """

    # Class-level declaration of handled Azure types
    # Subclasses MUST override this
    HANDLED_TYPES: ClassVar[Set[str]] = set()

    # Terraform resource type(s) this handler emits
    # Used for documentation and testing
    TERRAFORM_TYPES: ClassVar[Set[str]] = set()

    @classmethod
    def can_handle(cls, azure_type: str) -> bool:
        """Check if this handler can process the given Azure type.

        Args:
            azure_type: Azure resource type (e.g., "Microsoft.Compute/virtualMachines")

        Returns:
            True if handler can process this type
        """
        azure_type_lower = azure_type.lower()
        return any(t.lower() == azure_type_lower for t in cls.HANDLED_TYPES)

    @abstractmethod
    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure resource to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped

        Note:
            - Return None to skip the resource (with logging)
            - May add helper resources to context.terraform_config
            - Should validate references before emitting
        """
        raise NotImplementedError

    def post_emit(self, context: EmitterContext) -> None:  # noqa: B027
        """Called after all resources are emitted.

        Override to emit deferred resources like associations.
        Default implementation does nothing (intentional - not abstract).

        Args:
            context: Shared emitter context
        """

    # Utility methods available to all handlers

    @staticmethod
    def parse_properties(resource: Dict[str, Any]) -> Dict[str, Any]:
        """Parse JSON properties from resource.

        Args:
            resource: Azure resource dict with properties field

        Returns:
            Parsed properties dict (empty dict if parsing fails)
        """
        properties = resource.get("properties", "{}")
        if isinstance(properties, str):
            try:
                return json.loads(properties)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse properties for resource '{resource.get('name')}'"
                )
                return {}
        return properties if isinstance(properties, dict) else {}

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitize resource name for Terraform compatibility.

        Args:
            name: Original resource name

        Returns:
            Sanitized name safe for Terraform
        """
        # Replace invalid characters with underscores
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        # Ensure it starts with a letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = f"resource_{sanitized}"

        return sanitized or "unnamed_resource"

    @staticmethod
    def extract_name_from_id(resource_id: str, resource_type: str) -> str:
        """Extract resource name from Azure resource ID.

        Args:
            resource_id: Full Azure resource ID
            resource_type: Azure resource type segment (e.g., "subnets", "virtualNetworks")

        Returns:
            Extracted resource name or "unknown"
        """
        if not resource_id:
            return "unknown"

        path_segment = f"/{resource_type}/"
        if path_segment in resource_id:
            return resource_id.split(path_segment)[-1].split("/")[0]
        return "unknown"

    @staticmethod
    def parse_tags(tags: Any, resource_name: str) -> Optional[Dict[str, str]]:
        """Parse tags from resource.

        Args:
            tags: Tags field (string, dict, or None)
            resource_name: Resource name for logging

        Returns:
            Parsed tags dict or None
        """
        if tags is None:
            return None

        if isinstance(tags, dict):
            # Validate all values are strings
            if all(isinstance(v, str) for v in tags.values()):
                return tags if tags else None
            # Try to convert non-string values
            return {k: str(v) for k, v in tags.items()} if tags else None

        if isinstance(tags, str):
            try:
                parsed = json.loads(tags)
                if isinstance(parsed, dict) and parsed:
                    return {k: str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse tags JSON for resource '{resource_name}'"
                )

        return None

    @staticmethod
    def get_location(resource: Dict[str, Any], default: str = "eastus") -> str:
        """Get normalized location from resource.

        Args:
            resource: Azure resource dict
            default: Default location if not found or invalid

        Returns:
            Valid location string
        """
        location = resource.get("location")
        if not location or location.lower() in ["none", "null", "global"]:
            if location and location.lower() == "global":
                logger.warning(
                    f"Resource '{resource.get('name')}' has invalid location 'global', "
                    f"using '{default}' fallback"
                )
            return default
        return location

    @staticmethod
    def get_resource_group(resource: Dict[str, Any]) -> Optional[str]:
        """Get resource group name from resource.

        Args:
            resource: Azure resource dict

        Returns:
            Resource group name or None
        """
        return resource.get("resource_group") or resource.get("resourceGroup")

    def validate_resource_reference(
        self,
        terraform_type: str,
        name: str,
        context: EmitterContext,
    ) -> bool:
        """Validate that a referenced resource exists.

        Args:
            terraform_type: Terraform resource type
            name: Terraform resource name (sanitized)
            context: Emitter context with resource tracking

        Returns:
            True if resource exists in context or terraform config
        """
        # Check context tracking
        if context.resource_exists(terraform_type, name):
            return True

        # Check terraform config directly
        config_resources = context.terraform_config.get("resource", {})
        if terraform_type in config_resources:
            if name in config_resources[terraform_type]:
                return True

        return False

    def build_base_config(
        self,
        resource: Dict[str, Any],
        resource_name_with_suffix: Optional[str] = None,
        include_location: bool = True,
        context: Optional[Any] = None,  # Fix #601: Accept context for location override
    ) -> Dict[str, Any]:
        """Build base resource configuration with common fields.

        Args:
            resource: Azure resource dict
            resource_name_with_suffix: Optional name with unique suffix applied
            include_location: Whether to include location field (False for global resources)
            context: Optional EmitterContext for target_location override

        Returns:
            Base config with name, location (optional), resource_group_name
        """
        name = resource_name_with_suffix or resource.get("name", "unknown")
        rg_name = self.get_resource_group(resource)

        config = {
            "name": name,
            "resource_group_name": rg_name,
        }

        # Add location for resources that need it (most resources)
        if include_location:
            # Fix #601: Use target_location from context if provided, otherwise source location
            if context and hasattr(context, 'target_location') and context.target_location:
                location = context.target_location
            else:
                location = self.get_location(resource)
            config["location"] = location

        # Add tags if present
        tags = resource.get("tags")
        if tags:
            parsed_tags = self.parse_tags(tags, resource.get("name", "unknown"))
            if parsed_tags:
                config["tags"] = parsed_tags

        return config

    @staticmethod
    def normalize_cidr_block(cidr: str, context_name: str) -> Optional[str]:
        """Normalize a CIDR block to standard format.

        Args:
            cidr: CIDR block string
            context_name: Resource name for logging context

        Returns:
            Normalized CIDR or None if invalid
        """
        if not cidr or not isinstance(cidr, str):
            return None

        cidr = cidr.strip()

        # Basic validation
        if "/" not in cidr:
            logger.warning(f"CIDR '{cidr}' for '{context_name}' missing prefix length")
            return None

        try:
            ip_part, prefix_part = cidr.split("/")
            prefix = int(prefix_part)

            # Validate prefix length
            if prefix < 0 or prefix > 32:
                logger.warning(
                    f"CIDR '{cidr}' for '{context_name}' has invalid prefix: {prefix}"
                )
                return None

            # Validate IP parts
            parts = ip_part.split(".")
            if len(parts) != 4:
                logger.warning(
                    f"CIDR '{cidr}' for '{context_name}' has invalid IP format"
                )
                return None

            # Validate each octet
            for part in parts:
                octet = int(part)
                if octet < 0 or octet > 255:
                    logger.warning(
                        f"CIDR '{cidr}' for '{context_name}' has invalid octet: {octet}"
                    )
                    return None

            return cidr

        except (ValueError, AttributeError) as e:
            logger.warning(
                f"Failed to normalize CIDR '{cidr}' for '{context_name}': {e}"
            )
            return None
