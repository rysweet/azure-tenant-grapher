"""Data plane replication orchestration after control plane deployment."""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential, ClientSecretCredential

logger = logging.getLogger(__name__)


class ReplicationMode(Enum):
    """Data plane replication modes."""
    NONE = "none"
    TEMPLATE = "template"  # Structure only, no data
    REPLICATION = "replication"  # Full data copy


def orchestrate_dataplane_replication(
    iac_dir: Path,
    mode: ReplicationMode,
    source_tenant_id: str,
    target_tenant_id: str,
    source_subscription_id: str,
    target_subscription_id: str,
    sp_client_id: Optional[str] = None,
    sp_client_secret: Optional[str] = None,
) -> Dict[str, Any]:
    """Orchestrate data plane replication for all supported resources.

    Args:
        iac_dir: Directory containing deployed IaC (used to discover resources)
        mode: Replication mode (TEMPLATE or REPLICATION)
        source_tenant_id: Source Azure tenant ID
        target_tenant_id: Target Azure tenant ID
        source_subscription_id: Source subscription ID
        target_subscription_id: Target subscription ID
        sp_client_id: Optional service principal client ID
        sp_client_secret: Optional service principal client secret

    Returns:
        Dictionary with replication results:
        {
            "status": "success" | "partial" | "failed",
            "resources_processed": int,
            "plugins_executed": List[str],
            "errors": List[str],
            "warnings": List[str],
        }
    """
    if mode == ReplicationMode.NONE:
        logger.info("Data plane replication disabled (mode=none)")
        return {
            "status": "success",
            "resources_processed": 0,
            "plugins_executed": [],
            "errors": [],
            "warnings": ["Data plane replication skipped (mode=none)"],
        }

    logger.info(f"Starting data plane replication in {mode.value} mode")
    logger.info(f"Source: {source_tenant_id}/{source_subscription_id}")
    logger.info(f"Target: {target_tenant_id}/{target_subscription_id}")

    # Get credential
    if sp_client_id and sp_client_secret:
        logger.info("Using ClientSecretCredential with provided service principal")
        credential = ClientSecretCredential(
            tenant_id=target_tenant_id,
            client_id=sp_client_id,
            client_secret=sp_client_secret,
        )
    else:
        logger.info("Using DefaultAzureCredential")
        credential = DefaultAzureCredential()

    # Import plugins
    try:
        from src.iac.data_plane_plugins.vm_plugin import VMPlugin
        from src.iac.data_plane_plugins.acr_plugin import ContainerRegistryPlugin
        from src.iac.data_plane_plugins.cosmosdb_plugin import CosmosDBPlugin
        from src.iac.plugins.storage_plugin import StorageAccountPlugin
        from src.iac.plugins.keyvault_plugin import KeyVaultPlugin
        from src.iac.plugins.sql_plugin import SQLDatabasePlugin
        from src.iac.plugins.appservice_plugin import AppServicePlugin
        from src.iac.plugins.apim_plugin import APIManagementPlugin
    except ImportError as e:
        logger.error(f"Failed to import data plane plugins: {e}")
        return {
            "status": "failed",
            "resources_processed": 0,
            "plugins_executed": [],
            "errors": [f"Plugin import failed: {e}"],
            "warnings": [],
        }

    # Initialize plugins
    plugins = [
        ("VM", VMPlugin(credential)),
        ("ACR", ContainerRegistryPlugin(credential)),
        ("CosmosDB", CosmosDBPlugin(credential)),
        ("Storage", StorageAccountPlugin(credential)),
        ("KeyVault", KeyVaultPlugin(credential)),
        ("SQL", SQLDatabasePlugin(credential)),
        ("AppService", AppServicePlugin(credential)),
        ("APIManagement", APIManagementPlugin(credential)),
    ]

    # Discover resources from Neo4j or Azure
    # TODO: Query Neo4j for resources in target subscription
    # For now, use placeholder
    resources_to_replicate: List[Dict[str, Any]] = []

    # TODO: Query Neo4j:
    # MATCH (r:Resource {subscription_id: $target_sub})
    # WHERE r.type IN ['Microsoft.Compute/virtualMachines', ...]
    # RETURN r

    results = {
        "status": "success",
        "resources_processed": 0,
        "plugins_executed": [],
        "errors": [],
        "warnings": ["Data plane replication not yet fully integrated with Neo4j discovery"],
    }

    # Execute replication for each resource
    for resource in resources_to_replicate:
        resource_type = resource.get("type", "unknown")
        resource_id = resource.get("id", "unknown")

        # Find matching plugin
        matching_plugin = None
        for plugin_name, plugin in plugins:
            if plugin.can_handle(resource):
                matching_plugin = (plugin_name, plugin)
                break

        if not matching_plugin:
            logger.warning(f"No plugin found for {resource_type}: {resource_id}")
            results["warnings"].append(f"No plugin for {resource_type}")
            continue

        plugin_name, plugin = matching_plugin
        logger.info(f"Replicating {resource_type} with {plugin_name} plugin...")

        try:
            # Map source resource to target resource
            # TODO: Implement resource mapping logic
            source_resource_id = resource_id.replace(target_subscription_id, source_subscription_id)
            target_resource_id = resource_id

            # Execute replication
            success = plugin.replicate(
                source_resource={"id": source_resource_id},
                target_resource_id=target_resource_id,
            )

            if success:
                results["resources_processed"] += 1
                if plugin_name not in results["plugins_executed"]:
                    results["plugins_executed"].append(plugin_name)
            else:
                results["errors"].append(f"Failed to replicate {resource_id}")

        except Exception as e:
            logger.error(f"Error replicating {resource_id}: {e}")
            results["errors"].append(f"{resource_id}: {str(e)}")

    # Determine overall status
    if results["errors"]:
        if results["resources_processed"] > 0:
            results["status"] = "partial"
        else:
            results["status"] = "failed"

    logger.info(f"Data plane replication complete: {results['status']}")
    logger.info(f"Processed {results['resources_processed']} resources")
    logger.info(f"Executed plugins: {', '.join(results['plugins_executed'])}")

    if results["errors"]:
        logger.error(f"Errors: {len(results['errors'])}")
    if results["warnings"]:
        logger.warning(f"Warnings: {len(results['warnings'])}")

    return results
