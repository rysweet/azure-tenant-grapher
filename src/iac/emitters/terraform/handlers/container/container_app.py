"""Container App handlers for Terraform emission.

Handles: Microsoft.App/containerApps, Microsoft.App/managedEnvironments
Emits: azurerm_container_app, azurerm_container_app_environment
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ContainerAppEnvironmentHandler(ResourceHandler):
    """Handler for Azure Container App Environments.

    Emits:
        - azurerm_container_app_environment
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.App/managedEnvironments",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_container_app_environment",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Container App Environment to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)

        config = self.build_base_config(resource)

        logger.debug(f"Container App Environment '{resource_name}' emitted")

        return "azurerm_container_app_environment", safe_name, config


@handler
class ContainerAppHandler(ResourceHandler):
    """Handler for Azure Container Apps.

    Emits:
        - azurerm_container_app
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.App/containerApps",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_container_app",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Container App to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Container Apps: location is computed from environment - not configurable
        config = self.build_base_config(resource, include_location=False)

        # Container app environment ID - REQUIRED
        env_id = properties.get("managedEnvironmentId") or properties.get(
            "environmentId"
        )
        if not env_id:
            logger.warning(
                f"Container App '{resource_name}' missing required managedEnvironmentId, skipping"
            )
            return None

        # Prefer a Terraform reference if the environment was emitted in this run.
        # Otherwise translate the subscription ID so it points to the target subscription.
        env_name = self.extract_name_from_id(env_id, "managedEnvironments")
        if env_name and env_name != "unknown":
            env_safe = self.sanitize_name(env_name)
            emitted_envs = context.terraform_config.get("resource", {}).get(
                "azurerm_container_app_environment", {}
            )
            if env_safe in emitted_envs:
                config["container_app_environment_id"] = (
                    f"${{azurerm_container_app_environment.{env_safe}.id}}"
                )
                logger.debug(
                    f"Container App '{resource_name}' → environment ref: azurerm_container_app_environment.{env_safe}"
                )
            else:
                # Fall back: translate source subscription ID to target so the
                # Azure RM provider authenticates against the correct tenant.
                if context.source_subscription_id and context.target_subscription_id:
                    env_id = env_id.replace(
                        context.source_subscription_id, context.target_subscription_id
                    )
                config["container_app_environment_id"] = env_id
                logger.warning(
                    f"Container App '{resource_name}' environment '{env_name}' not in emitted config; "
                    f"using translated ID"
                )
        else:
            config["container_app_environment_id"] = env_id

        # Revision mode
        config["revision_mode"] = properties.get("configuration", {}).get(
            "activeRevisionsMode", "Single"
        )

        # Template
        template = properties.get("template", {})
        containers = template.get("containers", [])
        if containers:
            container = containers[0]
            config["template"] = {
                "container": {
                    "name": container.get("name", "container"),
                    "image": container.get(
                        "image",
                        "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest",
                    ),
                    "cpu": container.get("resources", {}).get("cpu", 0.25),
                    "memory": container.get("resources", {}).get("memory", "0.5Gi"),
                }
            }
        else:
            config["template"] = {
                "container": {
                    "name": "container",
                    "image": "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest",
                    "cpu": 0.25,
                    "memory": "0.5Gi",
                }
            }

        logger.debug(f"Container App '{resource_name}' emitted")

        return "azurerm_container_app", safe_name, config
