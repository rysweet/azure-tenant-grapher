"""Filter configuration model for Azure resource filtering."""

import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class FilterConfig(BaseModel):
    """Configuration for filtering Azure resources.

    Attributes:
        subscription_ids: List of subscription UUIDs to filter by (defaults to empty list)
        resource_group_names: List of resource group names to filter by (defaults to empty list)
    """

    subscription_ids: Optional[List[str]] = Field(default_factory=list)
    resource_group_names: Optional[List[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def convert_none_to_empty_list(cls, data: Any) -> Any:
        """Convert None values to empty lists before other validation."""
        if isinstance(data, dict):
            if data.get("subscription_ids") is None:
                data["subscription_ids"] = []
            if data.get("resource_group_names") is None:
                data["resource_group_names"] = []
        return data

    @field_validator("subscription_ids")
    @classmethod
    def validate_subscription_ids(cls, v: Optional[List[str]]) -> List[str]:
        """Validate that subscription IDs are valid UUIDs and remove duplicates."""
        if v is None:
            return []

        validated = []
        seen = set()
        for sub_id in v:
            try:
                # Validate UUID format
                UUID(sub_id)
                # Only add if not a duplicate
                if sub_id not in seen:
                    validated.append(sub_id)
                    seen.add(sub_id)
            except ValueError as e:
                raise ValueError(
                    f"Invalid subscription ID format: {sub_id}. Must be a valid UUID."
                ) from e

        return validated

    @field_validator("resource_group_names")
    @classmethod
    def validate_resource_group_names(cls, v: Optional[List[str]]) -> List[str]:
        """Validate resource group naming rules and remove duplicates.

        Azure resource group names must:
        - Be 1-90 characters long
        - Contain only alphanumeric characters, underscores, periods, hyphens, and parentheses
        - Start with an alphanumeric character
        - End with an alphanumeric character or underscore
        """
        if v is None:
            return []

        # Updated Azure resource group naming pattern to include parentheses
        pattern = re.compile(
            r"^[a-zA-Z0-9][a-zA-Z0-9._()-]{0,88}[a-zA-Z0-9_)]$|^[a-zA-Z0-9]$"
        )

        validated = []
        seen = set()
        for rg_name in v:
            if not pattern.match(rg_name):
                raise ValueError(
                    f"Invalid resource group name: {rg_name}. "
                    "Must be 1-90 characters, contain only alphanumeric, "
                    "underscores, periods, hyphens, and parentheses, and start with alphanumeric."
                )
            # Only add if not a duplicate
            if rg_name not in seen:
                validated.append(rg_name)
                seen.add(rg_name)

        return validated

    @classmethod
    def from_comma_separated(
        cls,
        subscription_ids: Optional[str] = None,
        resource_group_names: Optional[str] = None,
    ) -> "FilterConfig":
        """Create FilterConfig from comma-separated strings.

        This is useful for CLI parsing where arguments are provided as
        comma-separated values.

        Args:
            subscription_ids: Comma-separated string of subscription IDs
            resource_group_names: Comma-separated string of resource group names

        Returns:
            FilterConfig instance with parsed values
        """
        sub_ids = []
        if subscription_ids and subscription_ids.strip():
            # Split and strip whitespace, remove duplicates
            sub_ids = [s.strip() for s in subscription_ids.split(",") if s.strip()]

        rg_names = []
        if resource_group_names and resource_group_names.strip():
            # Split and strip whitespace, remove duplicates
            rg_names = [r.strip() for r in resource_group_names.split(",") if r.strip()]

        return cls(subscription_ids=sub_ids, resource_group_names=rg_names)

    def has_filters(self) -> bool:
        """Check if any filters are configured."""
        return bool(self.subscription_ids or self.resource_group_names)

    @property
    def is_empty(self) -> bool:
        """Check if no filters are configured (both lists are empty)."""
        return not self.subscription_ids and not self.resource_group_names

    def should_include_subscription(self, subscription_id: str) -> bool:
        """
        Check if a subscription should be included based on filters.

        Args:
            subscription_id: The subscription ID to check

        Returns:
            True if the subscription should be included, False otherwise
        """
        if not self.subscription_ids:
            return True
        return subscription_id in self.subscription_ids

    def should_include_resource_group(self, resource_group_name: str) -> bool:
        """
        Check if a resource group should be included based on filters.

        Args:
            resource_group_name: The resource group name to check

        Returns:
            True if the resource group should be included, False otherwise
        """
        if not self.resource_group_names:
            return True
        return resource_group_name in self.resource_group_names

    def should_include_resource(self, resource: Dict[str, Any]) -> bool:
        """
        Check if a resource should be included based on filters.

        Args:
            resource: The resource dictionary with 'id' field

        Returns:
            True if the resource should be included, False otherwise
        """
        if not self.has_filters():
            return True

        # Extract subscription ID and resource group from resource ID
        # Resource ID format: /subscriptions/{sub-id}/resourceGroups/{rg-name}/...
        resource_id = resource.get("id", "")
        parts = resource_id.split("/")

        # Check subscription filter
        if len(parts) > 2 and parts[1] == "subscriptions":
            subscription_id = parts[2]
            if self.subscription_ids and subscription_id not in self.subscription_ids:
                return False

        # Check resource group filter
        if len(parts) > 4 and parts[3] == "resourceGroups":
            resource_group = parts[4]
            if (
                self.resource_group_names
                and resource_group not in self.resource_group_names
            ):
                return False

        return True
