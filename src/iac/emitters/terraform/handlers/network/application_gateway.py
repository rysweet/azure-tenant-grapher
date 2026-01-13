"""Application Gateway handler for Terraform emission.

Handles: Microsoft.Network/applicationGateways
Emits: azurerm_application_gateway
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class ApplicationGatewayHandler(ResourceHandler):
    """Handler for Azure Application Gateways.

    Application Gateways require complex nested configuration blocks:
    - SKU configuration (name, tier, capacity)
    - Gateway IP configuration (subnet reference)
    - Frontend IP configuration (public IP reference)
    - Frontend ports
    - Backend address pools
    - Backend HTTP settings
    - HTTP listeners
    - Request routing rules

    Emits:
        - azurerm_application_gateway
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Network/applicationGateways",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_application_gateway",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure Application Gateway to Terraform configuration.

        Args:
            resource: Azure resource dictionary from graph
            context: Shared emitter context

        Returns:
            Tuple of (terraform_type, resource_name, config) or None if skipped
        """
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        # Build base config (name, location, resource_group_name, tags)
        config = self.build_base_config(resource)

        # Required: SKU block
        sku = self._build_sku_config(properties)
        config["sku"] = [sku]

        # Required: gateway_ip_configuration block
        gateway_ip_config = self._build_gateway_ip_config(
            properties, resource_name, context
        )
        if gateway_ip_config is None:
            return None  # Skip AppGW if subnet not found
        config["gateway_ip_configuration"] = [gateway_ip_config]

        # Required: frontend_ip_configuration block
        frontend_ip_config = self._build_frontend_ip_config(
            properties, resource_name, context
        )
        if frontend_ip_config is None:
            return None  # Skip AppGW if public IP not found
        config["frontend_ip_configuration"] = [frontend_ip_config]

        # Required: frontend_port blocks
        config["frontend_port"] = self._build_frontend_ports(properties)

        # Required: backend_address_pool blocks
        config["backend_address_pool"] = self._build_backend_pools(properties)

        # Required: backend_http_settings blocks
        config["backend_http_settings"] = self._build_backend_http_settings(properties)

        # Required: http_listener blocks
        config["http_listener"] = self._build_http_listeners(properties)

        # Required: request_routing_rule blocks
        config["request_routing_rule"] = self._build_routing_rules(properties)

        logger.debug(f"Application Gateway '{resource_name}' emitted")

        return "azurerm_application_gateway", safe_name, config

    def _build_sku_config(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Build SKU configuration block.

        Args:
            properties: Parsed properties dict

        Returns:
            SKU configuration dict
        """
        sku = properties.get("sku", {})
        if isinstance(sku, dict):
            sku_name = sku.get("name", "Standard_v2")
            sku_tier = sku.get("tier", "Standard_v2")
            sku_capacity = sku.get("capacity", 2)
        else:
            sku_name = "Standard_v2"
            sku_tier = "Standard_v2"
            sku_capacity = 2

        return {"name": sku_name, "tier": sku_tier, "capacity": sku_capacity}

    def _build_gateway_ip_config(
        self,
        properties: Dict[str, Any],
        resource_name: str,
        context: EmitterContext,
    ) -> Optional[Dict[str, Any]]:
        """Build gateway IP configuration block.

        Args:
            properties: Parsed properties dict
            resource_name: Resource name for logging
            context: Emitter context

        Returns:
            Gateway IP config dict or None if subnet not found
        """
        gateway_ip_configs = properties.get("gatewayIPConfigurations", [])
        if gateway_ip_configs:
            gateway_ip_config = (
                gateway_ip_configs[0] if isinstance(gateway_ip_configs, list) else {}
            )
            if isinstance(gateway_ip_config, dict):
                gateway_ip_name = gateway_ip_config.get("name", "gateway-ip-config")
                gateway_ip_props = gateway_ip_config.get("properties", {})
                subnet_id = gateway_ip_props.get("subnet", {}).get("id", "")
            else:
                gateway_ip_name = "gateway-ip-config"
                subnet_id = ""
        else:
            gateway_ip_name = "gateway-ip-config"
            subnet_id = ""

        # Resolve subnet reference - SKIP AppGW if subnet not found
        if not subnet_id:
            logger.warning(
                f"Skipping Application Gateway '{resource_name}': No subnet ID found in gatewayIPConfigurations"
            )
            return None

        subnet_reference = self._resolve_subnet_reference(
            subnet_id, resource_name, context
        )
        if subnet_reference is None:
            logger.warning(
                f"Skipping Application Gateway '{resource_name}': Cannot resolve subnet reference '{subnet_id}'"
            )
            return None

        return {"name": gateway_ip_name, "subnet_id": subnet_reference}

    def _build_frontend_ip_config(
        self,
        properties: Dict[str, Any],
        resource_name: str,
        context: EmitterContext,
    ) -> Optional[Dict[str, Any]]:
        """Build frontend IP configuration block.

        Args:
            properties: Parsed properties dict
            resource_name: Resource name for logging
            context: Emitter context

        Returns:
            Frontend IP config dict or None if public IP not found
        """
        frontend_ip_configs = properties.get("frontendIPConfigurations", [])
        if not frontend_ip_configs:
            logger.warning(
                f"Skipping Application Gateway '{resource_name}': No frontendIPConfigurations found"
            )
            return None

        frontend_ip_config = (
            frontend_ip_configs[0] if isinstance(frontend_ip_configs, list) else {}
        )
        if not isinstance(frontend_ip_config, dict):
            logger.warning(
                f"Skipping Application Gateway '{resource_name}': Invalid frontendIPConfiguration format"
            )
            return None

        frontend_ip_name = frontend_ip_config.get("name", "frontend-ip-config")
        frontend_ip_props = frontend_ip_config.get("properties", {})

        # Check for public IP - SKIP AppGW if not found or cannot be resolved
        public_ip_id = frontend_ip_props.get("publicIPAddress", {}).get("id", "")
        if not public_ip_id:
            logger.warning(
                f"Skipping Application Gateway '{resource_name}': No public IP ID found in frontendIPConfiguration"
            )
            return None

        public_ip_name = self.extract_name_from_id(public_ip_id, "publicIPAddresses")
        if public_ip_name == "unknown":
            logger.warning(
                f"Skipping Application Gateway '{resource_name}': Cannot extract public IP name from ID '{public_ip_id}'"
            )
            return None

        public_ip_name_safe = self.sanitize_name(public_ip_name)
        if not self.validate_resource_reference(
            "azurerm_public_ip", public_ip_name_safe, context
        ):
            logger.warning(
                f"Skipping Application Gateway '{resource_name}': Public IP '{public_ip_name}' does not exist in graph"
            )
            return None

        return {
            "name": frontend_ip_name,
            "public_ip_address_id": f"${{azurerm_public_ip.{public_ip_name_safe}.id}}",
        }

    def _build_frontend_ports(self, properties: Dict[str, Any]) -> list:
        """Build frontend port configuration blocks.

        Args:
            properties: Parsed properties dict

        Returns:
            List of frontend port config dicts
        """
        frontend_ports = properties.get("frontendPorts", [])
        if frontend_ports:
            frontend_port_blocks = []
            for port_config in frontend_ports:
                if isinstance(port_config, dict):
                    port_name = port_config.get("name", "frontend-port-80")
                    port_props = port_config.get("properties", {})
                    port_num = port_props.get("port", 80)
                else:
                    port_name = "frontend-port-80"
                    port_num = 80
                frontend_port_blocks.append({"name": port_name, "port": port_num})
            return frontend_port_blocks
        else:
            return [{"name": "frontend-port-80", "port": 80}]

    def _build_backend_pools(self, properties: Dict[str, Any]) -> list:
        """Build backend address pool configuration blocks.

        Args:
            properties: Parsed properties dict

        Returns:
            List of backend pool config dicts
        """
        backend_pools = properties.get("backendAddressPools", [])
        if backend_pools:
            backend_pool_blocks = []
            for pool_config in backend_pools:
                if isinstance(pool_config, dict):
                    pool_name = pool_config.get("name", "backend-pool")
                else:
                    pool_name = "backend-pool"
                backend_pool_blocks.append({"name": pool_name})
            return backend_pool_blocks
        else:
            return [{"name": "backend-pool"}]

    def _build_backend_http_settings(self, properties: Dict[str, Any]) -> list:
        """Build backend HTTP settings configuration blocks.

        Args:
            properties: Parsed properties dict

        Returns:
            List of backend HTTP settings config dicts
        """
        backend_http_settings = properties.get("backendHttpSettingsCollection", [])
        if backend_http_settings:
            backend_http_blocks = []
            for http_settings in backend_http_settings:
                if isinstance(http_settings, dict):
                    settings_name = http_settings.get("name", "backend-http-settings")
                    settings_props = http_settings.get("properties", {})
                    port = settings_props.get("port", 80)
                    protocol = settings_props.get("protocol", "Http")
                    cookie_affinity = settings_props.get(
                        "cookieBasedAffinity", "Disabled"
                    )
                    request_timeout = settings_props.get("requestTimeout", 60)
                else:
                    settings_name = "backend-http-settings"
                    port = 80
                    protocol = "Http"
                    cookie_affinity = "Disabled"
                    request_timeout = 60
                backend_http_blocks.append(
                    {
                        "name": settings_name,
                        "cookie_based_affinity": cookie_affinity,
                        "port": port,
                        "protocol": protocol,
                        "request_timeout": request_timeout,
                    }
                )
            return backend_http_blocks
        else:
            return [
                {
                    "name": "backend-http-settings",
                    "cookie_based_affinity": "Disabled",
                    "port": 80,
                    "protocol": "Http",
                    "request_timeout": 60,
                }
            ]

    def _build_http_listeners(self, properties: Dict[str, Any]) -> list:
        """Build HTTP listener configuration blocks.

        Args:
            properties: Parsed properties dict

        Returns:
            List of HTTP listener config dicts
        """
        http_listeners = properties.get("httpListeners", [])
        if http_listeners:
            http_listener_blocks = []
            for listener in http_listeners:
                if isinstance(listener, dict):
                    listener_name = listener.get("name", "http-listener")
                    listener_props = listener.get("properties", {})
                    frontend_ip_config_name = listener_props.get(
                        "frontendIPConfiguration", {}
                    ).get("id", "")
                    if frontend_ip_config_name:
                        frontend_ip_config_name = self.extract_name_from_id(
                            frontend_ip_config_name, "frontendIPConfigurations"
                        )
                    else:
                        frontend_ip_config_name = "frontend-ip-config"
                    frontend_port_name = listener_props.get("frontendPort", {}).get(
                        "id", ""
                    )
                    if frontend_port_name:
                        frontend_port_name = self.extract_name_from_id(
                            frontend_port_name, "frontendPorts"
                        )
                    else:
                        frontend_port_name = "frontend-port-80"
                    protocol = listener_props.get("protocol", "Http")
                else:
                    listener_name = "http-listener"
                    frontend_ip_config_name = "frontend-ip-config"
                    frontend_port_name = "frontend-port-80"
                    protocol = "Http"
                http_listener_blocks.append(
                    {
                        "name": listener_name,
                        "frontend_ip_configuration_name": frontend_ip_config_name,
                        "frontend_port_name": frontend_port_name,
                        "protocol": protocol,
                    }
                )
            return http_listener_blocks
        else:
            return [
                {
                    "name": "http-listener",
                    "frontend_ip_configuration_name": "frontend-ip-config",
                    "frontend_port_name": "frontend-port-80",
                    "protocol": "Http",
                }
            ]

    def _build_routing_rules(self, properties: Dict[str, Any]) -> list:
        """Build request routing rule configuration blocks.

        Args:
            properties: Parsed properties dict

        Returns:
            List of routing rule config dicts
        """
        routing_rules = properties.get("requestRoutingRules", [])
        if routing_rules:
            routing_rule_blocks = []
            priority = 100
            for rule in routing_rules:
                if isinstance(rule, dict):
                    rule_name = rule.get("name", "routing-rule")
                    rule_props = rule.get("properties", {})
                    rule_type = rule_props.get("ruleType", "Basic")
                    http_listener_name = rule_props.get("httpListener", {}).get(
                        "id", ""
                    )
                    if http_listener_name:
                        http_listener_name = self.extract_name_from_id(
                            http_listener_name, "httpListeners"
                        )
                    else:
                        http_listener_name = "http-listener"
                    backend_pool_name = rule_props.get("backendAddressPool", {}).get(
                        "id", ""
                    )
                    if backend_pool_name:
                        backend_pool_name = self.extract_name_from_id(
                            backend_pool_name, "backendAddressPools"
                        )
                    else:
                        backend_pool_name = "backend-pool"
                    backend_http_settings_name = rule_props.get(
                        "backendHttpSettings", {}
                    ).get("id", "")
                    if backend_http_settings_name:
                        backend_http_settings_name = self.extract_name_from_id(
                            backend_http_settings_name, "backendHttpSettingsCollection"
                        )
                    else:
                        backend_http_settings_name = "backend-http-settings"
                else:
                    rule_name = "routing-rule"
                    rule_type = "Basic"
                    http_listener_name = "http-listener"
                    backend_pool_name = "backend-pool"
                    backend_http_settings_name = "backend-http-settings"
                routing_rule_blocks.append(
                    {
                        "name": rule_name,
                        "rule_type": rule_type,
                        "http_listener_name": http_listener_name,
                        "backend_address_pool_name": backend_pool_name,
                        "backend_http_settings_name": backend_http_settings_name,
                        "priority": priority,
                    }
                )
                priority += 1
            return routing_rule_blocks
        else:
            return [
                {
                    "name": "routing-rule",
                    "rule_type": "Basic",
                    "http_listener_name": "http-listener",
                    "backend_address_pool_name": "backend-pool",
                    "backend_http_settings_name": "backend-http-settings",
                    "priority": 100,
                }
            ]

    def _resolve_subnet_reference(
        self,
        subnet_id: str,
        resource_name: str,
        context: EmitterContext,
    ) -> Optional[str]:
        """Resolve subnet reference to VNet-scoped Terraform resource name.

        Extracts both VNet and subnet names from Azure resource ID and constructs
        the scoped Terraform reference: ${azurerm_subnet.{vnet}_{subnet}.id}

        Args:
            subnet_id: Azure subnet resource ID
            resource_name: Name of resource referencing subnet (for logging)
            context: Emitter context

        Returns:
            Terraform reference string or None if subnet not found
        """
        if not subnet_id or "/subnets/" not in subnet_id:
            logger.warning(
                f"Resource '{resource_name}' has invalid subnet ID: {subnet_id}"
            )
            return None

        # Extract VNet name from ID
        vnet_name = self.extract_name_from_id(subnet_id, "virtualNetworks")
        if vnet_name == "unknown":
            logger.warning(
                f"Resource '{resource_name}' subnet ID missing VNet segment: {subnet_id}"
            )
            # Fallback: use only subnet name
            subnet_name = self.extract_name_from_id(subnet_id, "subnets")
            if subnet_name != "unknown":
                subnet_name_safe = self.sanitize_name(subnet_name)
                if (
                    context.available_subnets
                    and subnet_name_safe in context.available_subnets
                ):
                    return f"${{azurerm_subnet.{subnet_name_safe}.id}}"
            return None

        # Extract subnet name from ID
        subnet_name = self.extract_name_from_id(subnet_id, "subnets")
        if subnet_name == "unknown":
            logger.warning(
                f"Resource '{resource_name}' has invalid subnet name in ID: {subnet_id}"
            )
            return None

        # Build VNet-scoped subnet resource name
        vnet_safe = self.sanitize_name(vnet_name)
        subnet_safe = self.sanitize_name(subnet_name)
        scoped_subnet_name = f"{vnet_safe}_{subnet_safe}"

        # Check if subnet exists in context
        if (
            not context.available_subnets
            or scoped_subnet_name not in context.available_subnets
        ):
            logger.warning(
                f"Resource '{resource_name}' references non-existent subnet: {scoped_subnet_name}"
            )
            return None

        return f"${{azurerm_subnet.{scoped_subnet_name}.id}}"
