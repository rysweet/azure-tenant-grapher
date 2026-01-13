"""Azure Resource Provider Management.

This module provides functionality to detect, check, and register Azure resource providers
needed for IaC deployments. Many Azure resource providers are NotRegistered by default
in new/empty tenants, and must be registered before deploying resources.

Example:
    >>> manager = ProviderManager(subscription_id="sub-123")
    >>> required = manager.get_required_providers(terraform_config)
    >>> await manager.check_and_register_providers(required, auto=True)
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient

logger = logging.getLogger(__name__)


class ProviderState(str, Enum):
    """Azure resource provider registration states."""

    REGISTERED = "Registered"
    NOT_REGISTERED = "NotRegistered"
    REGISTERING = "Registering"
    UNREGISTERED = "Unregistered"
    UNKNOWN = "Unknown"


@dataclass
class ProviderStatus:
    """Status information for an Azure resource provider."""

    namespace: str
    state: ProviderState
    registration_state: Optional[str] = None


@dataclass
class ProviderCheckReport:
    """Report of provider registration check and actions."""

    subscription_id: str
    required_providers: Set[str]
    checked_providers: Dict[str, ProviderStatus]
    registered_providers: List[str]
    failed_providers: List[str]
    skipped_providers: List[str]

    def format_report(self) -> str:
        """Format the report as a human-readable string."""
        lines = []
        lines.append(f"\n{'=' * 60}")
        lines.append("AZURE RESOURCE PROVIDER CHECK REPORT")
        lines.append(f"{'=' * 60}")
        lines.append(f"Subscription: {self.subscription_id}")
        lines.append(f"Required Providers: {len(self.required_providers)}")
        lines.append(
            f"Already Registered: {len([p for p in self.checked_providers.values() if p.state == ProviderState.REGISTERED])}"
        )
        lines.append(f"Newly Registered: {len(self.registered_providers)}")
        lines.append(f"Failed: {len(self.failed_providers)}")
        lines.append(f"Skipped: {len(self.skipped_providers)}")

        if self.checked_providers:
            lines.append(f"\n{'Provider Status':40} {'State':20}")
            lines.append("-" * 60)
            for namespace, status in sorted(self.checked_providers.items()):
                state_str = status.state.value
                lines.append(f"{namespace:40} {state_str:20}")

        if self.registered_providers:
            lines.append(f"\nNewly Registered ({len(self.registered_providers)}):")
            for provider in sorted(self.registered_providers):
                lines.append(f"  ✓ {provider}")

        if self.failed_providers:
            lines.append(f"\nFailed to Register ({len(self.failed_providers)}):")
            for provider in sorted(self.failed_providers):
                lines.append(f"  ✗ {provider}")

        if self.skipped_providers:
            lines.append(f"\nSkipped ({len(self.skipped_providers)}):")
            for provider in sorted(self.skipped_providers):
                lines.append(f"  - {provider}")

        lines.append(f"{'=' * 60}\n")
        return "\n".join(lines)


class ProviderManager:
    """Manages Azure resource provider detection, checking, and registration."""

    # Mapping of Terraform resource types to Azure provider namespaces
    RESOURCE_TYPE_TO_PROVIDER = {
        # Compute
        "azurerm_virtual_machine": "Microsoft.Compute",
        "azurerm_linux_virtual_machine": "Microsoft.Compute",
        "azurerm_windows_virtual_machine": "Microsoft.Compute",
        "azurerm_virtual_machine_scale_set": "Microsoft.Compute",
        "azurerm_availability_set": "Microsoft.Compute",
        "azurerm_managed_disk": "Microsoft.Compute",
        "azurerm_disk_encryption_set": "Microsoft.Compute",
        "azurerm_image": "Microsoft.Compute",
        "azurerm_shared_image": "Microsoft.Compute",
        "azurerm_shared_image_gallery": "Microsoft.Compute",
        # Network
        "azurerm_virtual_network": "Microsoft.Network",
        "azurerm_subnet": "Microsoft.Network",
        "azurerm_network_interface": "Microsoft.Network",
        "azurerm_public_ip": "Microsoft.Network",
        "azurerm_network_security_group": "Microsoft.Network",
        "azurerm_network_security_rule": "Microsoft.Network",
        "azurerm_route_table": "Microsoft.Network",
        "azurerm_route": "Microsoft.Network",
        "azurerm_virtual_network_gateway": "Microsoft.Network",
        "azurerm_local_network_gateway": "Microsoft.Network",
        "azurerm_vpn_gateway": "Microsoft.Network",
        "azurerm_express_route_circuit": "Microsoft.Network",
        "azurerm_load_balancer": "Microsoft.Network",
        "azurerm_application_gateway": "Microsoft.Network",
        "azurerm_firewall": "Microsoft.Network",
        "azurerm_private_endpoint": "Microsoft.Network",
        "azurerm_private_dns_zone": "Microsoft.Network",
        "azurerm_dns_zone": "Microsoft.Network",
        # Storage
        "azurerm_storage_account": "Microsoft.Storage",
        "azurerm_storage_container": "Microsoft.Storage",
        "azurerm_storage_blob": "Microsoft.Storage",
        "azurerm_storage_queue": "Microsoft.Storage",
        "azurerm_storage_table": "Microsoft.Storage",
        "azurerm_storage_share": "Microsoft.Storage",
        # Key Vault
        "azurerm_key_vault": "Microsoft.KeyVault",
        "azurerm_key_vault_secret": "Microsoft.KeyVault",  # pragma: allowlist secret
        "azurerm_key_vault_key": "Microsoft.KeyVault",
        "azurerm_key_vault_certificate": "Microsoft.KeyVault",
        # SQL
        "azurerm_sql_server": "Microsoft.Sql",
        "azurerm_mssql_server": "Microsoft.Sql",
        "azurerm_mssql_database": "Microsoft.Sql",
        "azurerm_sql_database": "Microsoft.Sql",
        "azurerm_sql_elasticpool": "Microsoft.Sql",
        "azurerm_sql_firewall_rule": "Microsoft.Sql",
        # Web/App Service
        "azurerm_app_service": "Microsoft.Web",
        "azurerm_app_service_plan": "Microsoft.Web",
        "azurerm_linux_web_app": "Microsoft.Web",
        "azurerm_windows_web_app": "Microsoft.Web",
        "azurerm_function_app": "Microsoft.Web",
        "azurerm_linux_function_app": "Microsoft.Web",
        "azurerm_windows_function_app": "Microsoft.Web",
        # Container
        "azurerm_container_group": "Microsoft.ContainerInstance",
        "azurerm_kubernetes_cluster": "Microsoft.ContainerService",
        "azurerm_container_registry": "Microsoft.ContainerRegistry",
        # Monitoring
        "azurerm_monitor_action_group": "Microsoft.Insights",
        "azurerm_monitor_metric_alert": "Microsoft.Insights",
        "azurerm_monitor_diagnostic_setting": "Microsoft.Insights",
        "azurerm_log_analytics_workspace": "Microsoft.OperationalInsights",
        "azurerm_application_insights": "Microsoft.Insights",
        # API Management
        "azurerm_api_management": "Microsoft.ApiManagement",
        # Cosmos DB
        "azurerm_cosmosdb_account": "Microsoft.DocumentDB",
        "azurerm_cosmosdb_sql_database": "Microsoft.DocumentDB",
        # Service Bus
        "azurerm_servicebus_namespace": "Microsoft.ServiceBus",
        "azurerm_servicebus_queue": "Microsoft.ServiceBus",
        "azurerm_servicebus_topic": "Microsoft.ServiceBus",
        # Event Hub
        "azurerm_eventhub_namespace": "Microsoft.EventHub",
        "azurerm_eventhub": "Microsoft.EventHub",
        # Automation
        "azurerm_automation_account": "Microsoft.Automation",
        # Recovery Services
        "azurerm_recovery_services_vault": "Microsoft.RecoveryServices",
        "azurerm_backup_policy_vm": "Microsoft.RecoveryServices",
        # Logic Apps
        "azurerm_logic_app_workflow": "Microsoft.Logic",
        # Data Factory
        "azurerm_data_factory": "Microsoft.DataFactory",
        # Databricks
        "azurerm_databricks_workspace": "Microsoft.Databricks",
        # Resource Management (always needed)
        "azurerm_resource_group": "Microsoft.Resources",
        "azurerm_management_lock": "Microsoft.Authorization",
        "azurerm_role_assignment": "Microsoft.Authorization",
        "azurerm_role_definition": "Microsoft.Authorization",
    }

    def __init__(
        self,
        subscription_id: str,
        credential: Optional[Any] = None,
    ):
        """Initialize the provider manager.

        Args:
            subscription_id: Azure subscription ID to check/register providers
            credential: Azure credential (defaults to DefaultAzureCredential)
        """
        self.subscription_id = subscription_id
        self.credential = credential or DefaultAzureCredential()
        self._client: Optional[ResourceManagementClient] = None

    @property
    def client(self) -> ResourceManagementClient:
        """Lazy-load the Azure Resource Management client."""
        if self._client is None:
            self._client = ResourceManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id,
            )
        return self._client

    def get_required_providers(
        self,
        terraform_config: Optional[Dict[str, Any]] = None,
        terraform_path: Optional[Path] = None,
    ) -> Set[str]:
        """Extract required Azure provider namespaces from Terraform configuration.

        Args:
            terraform_config: Parsed Terraform configuration dictionary
            terraform_path: Path to Terraform files (will scan .tf files)

        Returns:
            Set of required provider namespaces (e.g., {'Microsoft.Compute', 'Microsoft.Network'})
        """
        required_providers: Set[str] = set()

        # Add core providers that are almost always needed
        required_providers.add("Microsoft.Resources")
        required_providers.add("Microsoft.Authorization")

        # Extract from terraform_config if provided
        if terraform_config:
            required_providers.update(
                self._extract_providers_from_config(terraform_config)
            )

        # Extract from terraform files if path provided
        if terraform_path:
            required_providers.update(
                self._extract_providers_from_files(terraform_path)
            )

        logger.info(str(f"Detected {len(required_providers)} required Azure providers"))
        logger.debug(str(f"Required providers: {sorted(required_providers)}"))

        return required_providers

    def _extract_providers_from_config(
        self, terraform_config: Dict[str, Any]
    ) -> Set[str]:
        """Extract provider namespaces from parsed Terraform config.

        Args:
            terraform_config: Parsed Terraform configuration

        Returns:
            Set of provider namespaces
        """
        providers: Set[str] = set()

        # Look for resource blocks
        if "resource" in terraform_config:
            for resource_type in terraform_config["resource"].keys():
                if provider := self._map_resource_to_provider(resource_type):
                    providers.add(provider)

        return providers

    def _extract_providers_from_files(self, terraform_path: Path) -> Set[str]:
        """Extract provider namespaces by scanning Terraform files.

        Args:
            terraform_path: Path to directory containing .tf files

        Returns:
            Set of provider namespaces
        """
        providers: Set[str] = set()

        if not terraform_path.exists():
            logger.warning(str(f"Terraform path does not exist: {terraform_path}"))
            return providers

        # Pattern to match Terraform resource declarations
        # Matches: resource "azurerm_virtual_machine" "example" {
        resource_pattern = re.compile(r'resource\s+"([^"]+)"\s+"[^"]+"')

        tf_files = list(terraform_path.glob("*.tf"))
        logger.debug(
            str(f"Scanning {len(tf_files)} Terraform files in {terraform_path}")
        )

        for tf_file in tf_files:
            try:
                content = tf_file.read_text()
                matches = resource_pattern.findall(content)

                for resource_type in matches:
                    if provider := self._map_resource_to_provider(resource_type):
                        providers.add(provider)

            except Exception as e:
                logger.warning(str(f"Error reading {tf_file}: {e}"))

        return providers

    def _map_resource_to_provider(self, resource_type: str) -> Optional[str]:
        """Map a Terraform resource type to its Azure provider namespace.

        Args:
            resource_type: Terraform resource type (e.g., "azurerm_virtual_machine")

        Returns:
            Provider namespace (e.g., "Microsoft.Compute") or None if not found
        """
        return self.RESOURCE_TYPE_TO_PROVIDER.get(resource_type)

    async def check_provider_status(
        self, providers: Set[str]
    ) -> Dict[str, ProviderStatus]:
        """Check registration state of specified providers.

        Args:
            providers: Set of provider namespaces to check

        Returns:
            Dictionary mapping provider namespace to ProviderStatus
        """
        status_map: Dict[str, ProviderStatus] = {}

        logger.info(str(f"Checking registration status for {len(providers)} providers"))

        for namespace in providers:
            try:
                provider = self.client.providers.get(namespace)
                state_str = provider.registration_state or "Unknown"

                # Map to our enum
                try:
                    state = ProviderState(state_str)
                except ValueError:
                    state = ProviderState.UNKNOWN

                status_map[namespace] = ProviderStatus(
                    namespace=namespace,
                    state=state,
                    registration_state=state_str,
                )

                logger.debug(str(f"Provider {namespace}: {state_str}"))

            except AzureError as e:
                logger.warning(str(f"Error checking provider {namespace}: {e}"))
                status_map[namespace] = ProviderStatus(
                    namespace=namespace,
                    state=ProviderState.UNKNOWN,
                )

        return status_map

    async def register_providers(
        self,
        providers: List[str],
        auto: bool = False,
    ) -> Dict[str, bool]:
        """Register specified Azure providers.

        Args:
            providers: List of provider namespaces to register
            auto: If True, register without prompting. If False, prompt user.

        Returns:
            Dictionary mapping provider namespace to success status
        """
        import click

        results: Dict[str, bool] = {}

        if not providers:
            logger.info("No providers to register")
            return results

        if not auto:
            click.echo(
                "\nThe following Azure resource providers need to be registered:"
            )
            for provider in sorted(providers):
                click.echo(f"  - {provider}")

            if not click.confirm(
                "\nDo you want to register these providers now?", default=True
            ):
                logger.info("Provider registration skipped by user")
                for provider in providers:
                    results[provider] = False
                return results

        logger.info(str(f"Registering {len(providers)} Azure providers..."))

        for namespace in providers:
            try:
                logger.info(str(f"Registering provider: {namespace}"))
                self.client.providers.register(namespace)
                results[namespace] = True
                logger.info(str(f"✓ Successfully registered: {namespace}"))

            except AzureError as e:
                logger.error(str(f"✗ Failed to register {namespace}: {e}"))
                results[namespace] = False

        return results

    async def check_and_register_providers(
        self,
        required_providers: Set[str],
        auto: bool = False,
    ) -> ProviderCheckReport:
        """Check provider status and register any that are not registered.

        Args:
            required_providers: Set of required provider namespaces
            auto: If True, automatically register providers without prompting

        Returns:
            ProviderCheckReport with detailed results
        """
        import click

        # Check current status
        status_map = await self.check_provider_status(required_providers)

        # Find providers that need registration
        needs_registration = [
            namespace
            for namespace, status in status_map.items()
            if status.state != ProviderState.REGISTERED
        ]

        registered_providers: List[str] = []
        failed_providers: List[str] = []
        skipped_providers: List[str] = []

        if needs_registration:
            click.echo(
                f"\n⚠️  Found {len(needs_registration)} providers that need registration"
            )

            # Register providers
            registration_results = await self.register_providers(
                needs_registration, auto=auto
            )

            for namespace, success in registration_results.items():
                if success:
                    registered_providers.append(namespace)
                    # Update status
                    status_map[namespace] = ProviderStatus(
                        namespace=namespace,
                        state=ProviderState.REGISTERED,
                    )
                elif registration_results[namespace] is False:
                    # User explicitly declined or registration failed
                    if auto:
                        failed_providers.append(namespace)
                    else:
                        skipped_providers.append(namespace)
        else:
            click.echo(
                f"\n✓ All {len(required_providers)} required providers are already registered"
            )

        return ProviderCheckReport(
            subscription_id=self.subscription_id,
            required_providers=required_providers,
            checked_providers=status_map,
            registered_providers=registered_providers,
            failed_providers=failed_providers,
            skipped_providers=skipped_providers,
        )

    async def validate_before_deploy(
        self,
        terraform_path: Path,
        auto_register: bool = False,
    ) -> ProviderCheckReport:
        """Pre-deployment validation - check and optionally register providers.

        This is the main entry point for provider validation before IaC deployment.

        Args:
            terraform_path: Path to Terraform files
            auto_register: If True, automatically register missing providers

        Returns:
            ProviderCheckReport with validation results
        """
        import click

        click.echo("\n🔍 Checking Azure resource provider registration...")

        # Detect required providers from Terraform files
        required_providers = self.get_required_providers(terraform_path=terraform_path)

        # Check and register if needed
        report = await self.check_and_register_providers(
            required_providers=required_providers,
            auto=auto_register,
        )

        return report
