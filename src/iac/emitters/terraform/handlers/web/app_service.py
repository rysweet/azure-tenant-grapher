"""App Service handler for Terraform emission.

Handles: Microsoft.Web/sites
Emits: azurerm_linux_web_app, azurerm_windows_web_app
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from src.services.azure_name_sanitizer import AzureNameSanitizer

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class AppServiceHandler(ResourceHandler):
    """Handler for Azure App Services.

    Emits:
        - azurerm_linux_web_app
        - azurerm_windows_web_app
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Web/sites",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_linux_web_app",
        "azurerm_windows_web_app",
    }

    def __init__(self):
        """Initialize handler with Azure name sanitizer."""
        super().__init__()
        self.sanitizer = AzureNameSanitizer()

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure App Service to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Determine if Linux or Windows
        kind = properties.get("kind", resource.get("kind", "")).lower()
        is_linux = "linux" in kind

        config = self.build_base_config(resource)

        # App Service names must be globally unique (*.azurewebsites.net)
        # Sanitize using centralized Azure naming rules
        abstracted_name = config["name"]
        sanitized_name = self.sanitizer.sanitize(abstracted_name, "Microsoft.Web/sites")

        # Add hash-based suffix for global uniqueness (works in all deployment modes)
        resource_id = resource.get("id", "")
        if resource_id:
            import hashlib

            hash_val = hashlib.md5(
                resource_id.encode(), usedforsecurity=False
            ).hexdigest()[:6]
            base_name = sanitized_name.replace("-", "").lower()
            if len(base_name) > 54:  # 60 char limit - 6 char hash
                base_name = base_name[:54]
            config["name"] = f"{base_name}{hash_val}"
            logger.info(
                f"App Service name made globally unique: {resource_name} → {config['name']}"
            )
        else:
            config["name"] = sanitized_name

        # Build site_config block
        site_config = {}
        site_config_props = properties.get("siteConfig", {})

        if is_linux and "linuxFxVersion" in site_config_props:
            site_config["application_stack"] = {
                "docker_image": site_config_props["linuxFxVersion"]
            }

        # Service plan ID
        service_plan_id = resource.get("app_service_plan_id")
        if not service_plan_id:
            # Create a default service plan
            rg = self.get_resource_group(resource)
            plan_name = f"{resource_name}-plan"
            plan_safe_name = self.sanitize_name(plan_name)
            location = self.get_location(resource)

            context.add_helper_resource(
                "azurerm_service_plan",
                plan_safe_name,
                {
                    "name": plan_name,
                    "location": location,
                    "resource_group_name": rg,
                    "os_type": "Linux" if is_linux else "Windows",
                    "sku_name": "B1",
                },
            )

            service_plan_id = f"${{azurerm_service_plan.{plan_safe_name}.id}}"
            logger.debug(
                f"Created default service plan '{plan_name}' for App Service '{resource_name}'"
            )

        config.update(
            {
                "service_plan_id": service_plan_id,
                "site_config": site_config if site_config else {},
            }
        )

        terraform_type = (
            "azurerm_linux_web_app" if is_linux else "azurerm_windows_web_app"
        )

        logger.debug(f"App Service '{resource_name}' emitted as {terraform_type}")

        return terraform_type, safe_name, config
