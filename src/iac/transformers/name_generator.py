"""Unique name generator for globally unique Azure resources.

This module generates globally unique names for Key Vaults and Storage Accounts,
preventing naming conflicts (97 errors: 52 Key Vault + 45 Storage).

Azure naming constraints:
- Key Vault: 3-24 chars, alphanumeric and hyphens, must start with letter
- Storage Account: 3-24 chars, lowercase alphanumeric only, globally unique
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NameGenerationResult:
    """Result of name generation operation."""

    resources_processed: int
    resources_renamed: int
    renames: List[tuple[str, str, str]] = None  # (resource_id, old_name, new_name)

    def __post_init__(self):
        if self.renames is None:
            self.renames = []


class UniqueNameGenerator:
    """Generate globally unique names for Key Vaults and Storage Accounts.

    Uses deterministic hashing to generate unique names that respect
    Azure naming constraints.
    """

    # Resource types that require globally unique names
    GLOBALLY_UNIQUE_TYPES = {
        "Microsoft.KeyVault/vaults",
        "Microsoft.Storage/storageAccounts",
    }

    # Naming constraints
    KEYVAULT_MAX_LENGTH = 24
    KEYVAULT_MIN_LENGTH = 3
    STORAGE_MAX_LENGTH = 24
    STORAGE_MIN_LENGTH = 3

    def __init__(self, suffix: Optional[str] = None) -> None:
        """Initialize unique name generator.

        Args:
            suffix: Optional suffix to append to generated names
        """
        self.suffix = suffix
        logger.info(f"UniqueNameGenerator initialized: suffix={suffix}")

    def transform_resources(self, resources: List[Dict[str, Any]]) -> NameGenerationResult:
        """Transform resources by generating unique names.

        Args:
            resources: List of resources to transform (modified in place)

        Returns:
            NameGenerationResult with transformation statistics
        """
        resources_processed = 0
        resources_renamed = 0
        renames = []

        for resource in resources:
            resources_processed += 1

            resource_type = resource.get("type", "")
            resource_id = resource.get("id", "unknown")
            original_name = resource.get("name", "")

            # Only process globally unique resource types
            if resource_type not in self.GLOBALLY_UNIQUE_TYPES:
                continue

            # Generate unique name based on resource type
            if resource_type == "Microsoft.KeyVault/vaults":
                new_name = self._generate_keyvault_name(resource_id, original_name)
            elif resource_type == "Microsoft.Storage/storageAccounts":
                new_name = self._generate_storage_name(resource_id, original_name)
            else:
                continue

            # Apply new name
            if new_name != original_name:
                resource["name"] = new_name
                resources_renamed += 1
                renames.append((resource_id, original_name, new_name))

                logger.info(
                    f"Renamed {resource_type} '{original_name}' -> '{new_name}' "
                    f"(resource_id: {resource_id})"
                )

        logger.info(
            f"Name generation complete: {resources_processed} processed, "
            f"{resources_renamed} renamed"
        )

        return NameGenerationResult(
            resources_processed=resources_processed,
            resources_renamed=resources_renamed,
            renames=renames,
        )

    def _generate_keyvault_name(self, resource_id: str, original_name: str) -> str:
        """Generate unique Key Vault name.

        Constraints:
        - 3-24 characters
        - Alphanumeric and hyphens
        - Must start with letter
        - Must end with alphanumeric

        Args:
            resource_id: Resource ID for deterministic hashing
            original_name: Original resource name

        Returns:
            Generated unique name
        """
        # Clean original name (remove invalid chars)
        clean_name = re.sub(r"[^a-zA-Z0-9-]", "", original_name)
        clean_name = re.sub(r"-+", "-", clean_name)  # Collapse multiple hyphens

        # Ensure starts with letter
        if not clean_name or not clean_name[0].isalpha():
            clean_name = "kv-" + clean_name

        # Generate hash for uniqueness (8 chars)
        hash_input = f"{resource_id}:{original_name}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]

        # Apply suffix if provided
        if self.suffix:
            suffix_clean = re.sub(r"[^a-zA-Z0-9-]", "", self.suffix)
            base_name = f"{clean_name}-{suffix_clean}"
        else:
            base_name = clean_name

        # Combine: base-hash (ensure <= 24 chars)
        max_base_length = self.KEYVAULT_MAX_LENGTH - len(hash_value) - 1  # -1 for hyphen
        if len(base_name) > max_base_length:
            base_name = base_name[:max_base_length]

        # Remove trailing hyphen if present
        base_name = base_name.rstrip("-")

        unique_name = f"{base_name}-{hash_value}"

        # Ensure minimum length
        if len(unique_name) < self.KEYVAULT_MIN_LENGTH:
            unique_name = unique_name + "x" * (self.KEYVAULT_MIN_LENGTH - len(unique_name))

        # Ensure maximum length
        if len(unique_name) > self.KEYVAULT_MAX_LENGTH:
            unique_name = unique_name[: self.KEYVAULT_MAX_LENGTH]

        # Ensure ends with alphanumeric
        unique_name = unique_name.rstrip("-")

        return unique_name

    def _generate_storage_name(self, resource_id: str, original_name: str) -> str:
        """Generate unique Storage Account name.

        Constraints:
        - 3-24 characters
        - Lowercase alphanumeric only
        - Globally unique

        Args:
            resource_id: Resource ID for deterministic hashing
            original_name: Original resource name

        Returns:
            Generated unique name
        """
        # Clean original name (lowercase alphanumeric only)
        clean_name = re.sub(r"[^a-z0-9]", "", original_name.lower())

        # Generate hash for uniqueness (8 chars)
        hash_input = f"{resource_id}:{original_name}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]

        # Apply suffix if provided
        if self.suffix:
            suffix_clean = re.sub(r"[^a-z0-9]", "", self.suffix.lower())
            base_name = f"{clean_name}{suffix_clean}"
        else:
            base_name = clean_name

        # Combine: base + hash (ensure <= 24 chars)
        max_base_length = self.STORAGE_MAX_LENGTH - len(hash_value)
        if len(base_name) > max_base_length:
            base_name = base_name[:max_base_length]

        unique_name = f"{base_name}{hash_value}"

        # Ensure minimum length
        if len(unique_name) < self.STORAGE_MIN_LENGTH:
            unique_name = unique_name + "x" * (self.STORAGE_MIN_LENGTH - len(unique_name))

        # Ensure maximum length
        if len(unique_name) > self.STORAGE_MAX_LENGTH:
            unique_name = unique_name[: self.STORAGE_MAX_LENGTH]

        return unique_name

    def get_generation_summary(self, result: NameGenerationResult) -> str:
        """Generate human-readable summary of name generation results.

        Args:
            result: Name generation result to summarize

        Returns:
            Formatted summary string
        """
        summary = [
            "Unique Name Generator Summary",
            "=" * 50,
            f"Resources processed: {result.resources_processed}",
            f"Resources renamed: {result.resources_renamed}",
            "",
        ]

        if result.renames:
            summary.append("Name Changes:")
            for resource_id, old_name, new_name in result.renames:
                summary.append(f"  - {old_name} -> {new_name}")
                summary.append(f"    Resource: {resource_id}")

        return "\n".join(summary)
