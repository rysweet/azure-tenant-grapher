"""EmitterContext - Shared state passed to all handlers during emission.

This module contains the EmitterContext dataclass that encapsulates all
shared state and configuration needed by resource handlers during
Terraform template generation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class EmitterContext:
    """Shared context passed to all handlers during emission.

    This dataclass encapsulates all shared state that handlers need:
    - Target configuration (subscription, tenant IDs)
    - Terraform config being built
    - Resource tracking for reference validation
    - Association tracking for deferred resource emission
    - Error tracking for missing references

    Usage:
        context = EmitterContext(
            target_subscription_id="xxx",
            target_tenant_id="yyy",
        )
        handler.emit(resource, context)
    """

    # Target configuration
    target_subscription_id: Optional[str] = None
    target_tenant_id: Optional[str] = None
    target_location: Optional[str] = None  # Fix #601: Target region override
    source_subscription_id: Optional[str] = None
    source_tenant_id: Optional[str] = None
    identity_mapping: Optional[Dict[str, Any]] = None
    resource_group_prefix: str = ""
    strict_mode: bool = False

    # Terraform config being built
    terraform_config: Dict[str, Any] = field(default_factory=dict)

    # Resource tracking for reference validation
    available_resources: Dict[str, Set[str]] = field(default_factory=dict)
    available_subnets: Set[str] = field(default_factory=set)
    available_resource_groups: Set[str] = field(default_factory=set)

    # VNet ID mapping for subnet references (Bug #31)
    vnet_id_to_terraform_name: Dict[str, str] = field(default_factory=dict)

    # Association tracking (emitted after main resources)
    nsg_associations: List[tuple] = field(default_factory=list)
    nic_nsg_associations: List[tuple] = field(default_factory=list)

    # Error tracking
    missing_references: List[Dict[str, str]] = field(default_factory=list)

    # Graph reference for validation
    graph: Optional[Any] = None

    # Translation coordinator
    translation_coordinator: Optional[Any] = None

    def add_resource(self, terraform_type: str, name: str) -> None:
        """Track a resource that will be emitted.

        Args:
            terraform_type: Terraform resource type (e.g., "azurerm_virtual_network")
            name: Terraform resource name (sanitized)
        """
        if terraform_type not in self.available_resources:
            self.available_resources[terraform_type] = set()
        self.available_resources[terraform_type].add(name)

    def resource_exists(self, terraform_type: str, name: str) -> bool:
        """Check if a resource exists in tracking.

        Args:
            terraform_type: Terraform resource type
            name: Terraform resource name (sanitized)

        Returns:
            True if resource is being tracked
        """
        return name in self.available_resources.get(terraform_type, set())

    def add_helper_resource(
        self,
        resource_type: str,
        name: str,
        config: Dict[str, Any],
    ) -> None:
        """Add a helper resource to terraform config.

        Helper resources are additional resources generated alongside
        the main resource (e.g., SSH keys for VMs, passwords for SQL servers).

        Args:
            resource_type: Terraform resource type (e.g., "tls_private_key")
            name: Resource name
            config: Resource configuration dict
        """
        if "resource" not in self.terraform_config:
            self.terraform_config["resource"] = {}
        if resource_type not in self.terraform_config["resource"]:
            self.terraform_config["resource"][resource_type] = {}
        self.terraform_config["resource"][resource_type][name] = config

    def add_data_source(
        self,
        data_type: str,
        name: str,
        config: Dict[str, Any],
    ) -> None:
        """Add a data source to terraform config.

        Data sources allow referencing existing Azure resources
        (e.g., Key Vault secrets, existing VNets).

        Args:
            data_type: Terraform data source type (e.g., "azurerm_key_vault_secret")
            name: Data source name
            config: Data source configuration dict

        Example:
            context.add_data_source(
                "azurerm_key_vault_secret",
                "vm_admin_password",
                {
                    "name": "vm-admin-password",
                    "key_vault_id": "${data.azurerm_key_vault.main.id}",
                },
            )
        """
        if "data" not in self.terraform_config:
            self.terraform_config["data"] = {}
        if data_type not in self.terraform_config["data"]:
            self.terraform_config["data"][data_type] = {}
        self.terraform_config["data"][data_type][name] = config

    def get_effective_subscription_id(self, resource: Dict[str, Any]) -> str:
        """Get the subscription ID to use for resource construction.

        In cross-tenant mode, returns target subscription ID.
        Otherwise returns the resource's original subscription ID.

        Args:
            resource: Resource dictionary with subscription_id field

        Returns:
            Subscription ID to use in constructed resource IDs
        """
        if self.target_subscription_id:
            return self.target_subscription_id
        return resource.get("subscription_id", "")

    def track_nsg_association(
        self,
        subnet_tf_name: str,
        nsg_tf_name: str,
        subnet_name: str,
        nsg_name: str,
    ) -> None:
        """Track an NSG-subnet association for deferred emission.

        Args:
            subnet_tf_name: Terraform name for subnet
            nsg_tf_name: Terraform name for NSG
            subnet_name: Original Azure subnet name
            nsg_name: Original Azure NSG name
        """
        self.nsg_associations.append(
            (subnet_tf_name, nsg_tf_name, subnet_name, nsg_name)
        )

    def track_nic_nsg_association(
        self,
        nic_tf_name: str,
        nsg_tf_name: str,
        nic_name: str,
        nsg_name: str,
    ) -> None:
        """Track a NIC-NSG association for deferred emission.

        Args:
            nic_tf_name: Terraform name for NIC
            nsg_tf_name: Terraform name for NSG
            nic_name: Original Azure NIC name
            nsg_name: Original Azure NSG name
        """
        self.nic_nsg_associations.append((nic_tf_name, nsg_tf_name, nic_name, nsg_name))

    def track_missing_reference(
        self,
        resource_name: str,
        resource_type: str,
        missing_resource_name: str,
        missing_resource_id: str,
        **extra: Any,
    ) -> None:
        """Track a missing resource reference for reporting.

        Args:
            resource_name: Name of resource with missing reference
            resource_type: Type of missing resource
            missing_resource_name: Name of missing resource
            missing_resource_id: Azure ID of missing resource
            **extra: Additional context fields
        """
        ref_info = {
            "resource_name": resource_name,
            "resource_type": resource_type,
            "missing_resource_name": missing_resource_name,
            "missing_resource_id": missing_resource_id,
        }
        ref_info.update(extra)
        self.missing_references.append(ref_info)
