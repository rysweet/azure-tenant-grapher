"""Tests for Application Gateway resource conversion in TerraformEmitter.

This module tests the Application Gateway conversion which requires complex
nested configuration blocks (sku, gateway_ip_configuration, frontend_ip_configuration,
frontend_port, backend_address_pool, backend_http_settings, http_listener,
request_routing_rule).

These tests verify that all required blocks are generated with proper defaults
when properties are missing or incomplete.
"""

import json

from src.iac.emitters.terraform_emitter import TerraformEmitter


def setup_appgw_dependencies(emitter):
    """Set up minimal dependencies for AppGW to succeed.

    After bug fix, AppGWs require valid subnet and public IP references.
    """
    emitter._available_subnets = {"test_vnet_appgw_subnet"}
    emitter._available_resources = {"azurerm_public_ip": {"test_pip"}}


def get_minimal_appgw_properties():
    """Get minimal AppGW properties with valid subnet and public IP references."""
    return {
        "gatewayIPConfigurations": [
            {
                "name": "gateway-ip-config",
                "properties": {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/appgw-subnet"
                    }
                }
            }
        ],
        "frontendIPConfigurations": [
            {
                "name": "frontend-ip-config",
                "properties": {
                    "publicIPAddress": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-pip"
                    }
                }
            }
        ]
    }


class TestApplicationGatewayMapping:
    """Test Application Gateway resource type mapping."""

    def test_application_gateway_mapping(self):
        """Test Microsoft.Network/applicationGateways mapping."""
        emitter = TerraformEmitter()
        assert (
            "Microsoft.Network/applicationGateways"
            in emitter.AZURE_TO_TERRAFORM_MAPPING
        )
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING[
                "Microsoft.Network/applicationGateways"
            ]
            == "azurerm_application_gateway"
        )


class TestApplicationGatewayConversion:
    """Test Application Gateway conversion with all required blocks."""

    def test_minimal_application_gateway(self):
        """Test converting Application Gateway with minimal properties.

        NOTE: After bug fix, AppGWs without valid subnet/public IP references
        are now SKIPPED. This test now expects None result for minimal config.

        To succeed, AppGW needs valid subnet and public IP references.
        See TestApplicationGatewaySkippingBehavior.test_appgw_succeeds_with_valid_dependencies
        """
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({}),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        # After bug fix: minimal AppGW is now skipped due to missing dependencies
        assert result is None

    def test_minimal_application_gateway_with_dependencies(self):
        """Test converting Application Gateway with minimal properties but valid dependencies.

        Verifies that all 8 required blocks are generated with defaults
        when Azure properties are present but minimal.
        """
        emitter = TerraformEmitter()
        # Set up valid dependencies
        emitter._available_subnets = {"test_vnet_appgw_subnet"}
        emitter._available_resources = {"azurerm_public_ip": {"test_pip"}}

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "gatewayIPConfigurations": [
                    {
                        "name": "gateway-ip-config",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/appgw-subnet"
                            }
                        }
                    }
                ],
                "frontendIPConfigurations": [
                    {
                        "name": "frontend-ip-config",
                        "properties": {
                            "publicIPAddress": {
                                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-pip"
                            }
                        }
                    }
                ]
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify resource type and name
        assert terraform_type == "azurerm_application_gateway"
        assert safe_name == "test_appgw"

        # Verify all 8 required blocks exist
        assert "sku" in config
        assert "gateway_ip_configuration" in config
        assert "frontend_ip_configuration" in config
        assert "frontend_port" in config
        assert "backend_address_pool" in config
        assert "backend_http_settings" in config
        assert "http_listener" in config
        assert "request_routing_rule" in config

        # Verify sku block structure
        assert isinstance(config["sku"], list)
        assert len(config["sku"]) == 1
        assert config["sku"][0]["name"] == "Standard_v2"
        assert config["sku"][0]["tier"] == "Standard_v2"
        assert config["sku"][0]["capacity"] == 2

        # Verify gateway_ip_configuration block
        assert isinstance(config["gateway_ip_configuration"], list)
        assert len(config["gateway_ip_configuration"]) == 1
        assert "name" in config["gateway_ip_configuration"][0]
        assert "subnet_id" in config["gateway_ip_configuration"][0]

        # Verify frontend_ip_configuration block
        assert isinstance(config["frontend_ip_configuration"], list)
        assert len(config["frontend_ip_configuration"]) == 1
        assert "name" in config["frontend_ip_configuration"][0]
        assert "public_ip_address_id" in config["frontend_ip_configuration"][0]

        # Verify frontend_port block
        assert isinstance(config["frontend_port"], list)
        assert len(config["frontend_port"]) == 1
        assert config["frontend_port"][0]["name"] == "frontend-port-80"
        assert config["frontend_port"][0]["port"] == 80

        # Verify backend_address_pool block
        assert isinstance(config["backend_address_pool"], list)
        assert len(config["backend_address_pool"]) == 1
        assert config["backend_address_pool"][0]["name"] == "backend-pool"

        # Verify backend_http_settings block
        assert isinstance(config["backend_http_settings"], list)
        assert len(config["backend_http_settings"]) == 1
        assert config["backend_http_settings"][0]["name"] == "backend-http-settings"
        assert config["backend_http_settings"][0]["cookie_based_affinity"] == "Disabled"
        assert config["backend_http_settings"][0]["port"] == 80
        assert config["backend_http_settings"][0]["protocol"] == "Http"
        assert config["backend_http_settings"][0]["request_timeout"] == 60

        # Verify http_listener block
        assert isinstance(config["http_listener"], list)
        assert len(config["http_listener"]) == 1
        assert config["http_listener"][0]["name"] == "http-listener"
        assert (
            config["http_listener"][0]["frontend_ip_configuration_name"]
            == "frontend-ip-config"
        )
        assert (
            config["http_listener"][0]["frontend_port_name"]
            == "frontend-port-80"
        )
        assert config["http_listener"][0]["protocol"] == "Http"

        # Verify request_routing_rule block
        assert isinstance(config["request_routing_rule"], list)
        assert len(config["request_routing_rule"]) == 1
        assert config["request_routing_rule"][0]["name"] == "routing-rule"
        assert config["request_routing_rule"][0]["rule_type"] == "Basic"
        assert (
            config["request_routing_rule"][0]["http_listener_name"]
            == "http-listener"
        )
        assert (
            config["request_routing_rule"][0]["backend_address_pool_name"]
            == "backend-pool"
        )
        assert (
            config["request_routing_rule"][0]["backend_http_settings_name"]
            == "backend-http-settings"
        )
        assert config["request_routing_rule"][0]["priority"] == 100

    def test_application_gateway_with_custom_sku(self):
        """Test Application Gateway with custom SKU configuration."""
        emitter = TerraformEmitter()
        setup_appgw_dependencies(emitter)

        properties = get_minimal_appgw_properties()
        properties["sku"] = {
            "name": "WAF_v2",
            "tier": "WAF_v2",
            "capacity": 4
        }

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "westus",
            "resource_group": "test-rg",
            "properties": json.dumps(properties),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify custom SKU is used
        assert config["sku"][0]["name"] == "WAF_v2"
        assert config["sku"][0]["tier"] == "WAF_v2"
        assert config["sku"][0]["capacity"] == 4

    def test_application_gateway_with_multiple_frontend_ports(self):
        """Test Application Gateway with multiple frontend ports."""
        emitter = TerraformEmitter()
        setup_appgw_dependencies(emitter)

        properties = get_minimal_appgw_properties()
        properties["frontendPorts"] = [
            {
                "name": "port-80",
                "properties": {"port": 80}
            },
            {
                "name": "port-443",
                "properties": {"port": 443}
            }
        ]

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(properties),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify multiple frontend ports
        assert len(config["frontend_port"]) == 2
        assert config["frontend_port"][0]["port"] == 80
        assert config["frontend_port"][1]["port"] == 443

    def test_application_gateway_with_multiple_backend_pools(self):
        """Test Application Gateway with multiple backend address pools."""
        emitter = TerraformEmitter()
        setup_appgw_dependencies(emitter)

        properties = get_minimal_appgw_properties()
        properties["backendAddressPools"] = [
            {"name": "backend-pool-1"},
            {"name": "backend-pool-2"}
        ]

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(properties),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify multiple backend pools
        assert len(config["backend_address_pool"]) == 2
        assert config["backend_address_pool"][0]["name"] == "backend-pool-1"
        assert config["backend_address_pool"][1]["name"] == "backend-pool-2"

    def test_application_gateway_with_https_listener(self):
        """Test Application Gateway with HTTPS listener configuration."""
        emitter = TerraformEmitter()
        setup_appgw_dependencies(emitter)

        properties = get_minimal_appgw_properties()
        properties["httpListeners"] = [
            {
                "name": "https-listener",
                "properties": {
                    "protocol": "Https"
                }
            }
        ]

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(properties),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify HTTPS listener protocol
        assert len(config["http_listener"]) == 1
        assert config["http_listener"][0]["protocol"] == "Https"

    def test_application_gateway_with_custom_backend_http_settings(self):
        """Test Application Gateway with custom backend HTTP settings."""
        emitter = TerraformEmitter()
        setup_appgw_dependencies(emitter)

        properties = get_minimal_appgw_properties()
        properties["backendHttpSettingsCollection"] = [
            {
                "name": "custom-settings",
                "properties": {
                    "port": 8080,
                    "protocol": "Https",
                    "cookieBasedAffinity": "Enabled",
                    "requestTimeout": 120
                }
            }
        ]

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(properties),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify custom backend HTTP settings
        assert len(config["backend_http_settings"]) == 1
        settings = config["backend_http_settings"][0]
        assert settings["name"] == "custom-settings"
        assert settings["port"] == 8080
        assert settings["protocol"] == "Https"
        assert settings["cookie_based_affinity"] == "Enabled"
        assert settings["request_timeout"] == 120

    def test_application_gateway_with_request_routing_rules(self):
        """Test Application Gateway with multiple request routing rules."""
        emitter = TerraformEmitter()
        setup_appgw_dependencies(emitter)

        properties = get_minimal_appgw_properties()
        properties["requestRoutingRules"] = [
            {
                "name": "rule-1",
                "properties": {
                    "ruleType": "Basic"
                }
            },
            {
                "name": "rule-2",
                "properties": {
                    "ruleType": "PathBasedRouting"
                }
            }
        ]

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(properties),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify multiple routing rules with incremented priorities
        assert len(config["request_routing_rule"]) == 2
        assert config["request_routing_rule"][0]["name"] == "rule-1"
        assert config["request_routing_rule"][0]["rule_type"] == "Basic"
        assert config["request_routing_rule"][0]["priority"] == 100
        assert config["request_routing_rule"][1]["name"] == "rule-2"
        assert config["request_routing_rule"][1]["rule_type"] == "PathBasedRouting"
        assert config["request_routing_rule"][1]["priority"] == 101

    def test_application_gateway_sanitizes_name(self):
        """Test that Application Gateway name is properly sanitized."""
        emitter = TerraformEmitter()
        setup_appgw_dependencies(emitter)

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw-123",
            "name": "test-appgw-123",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(get_minimal_appgw_properties()),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify name is sanitized (hyphens replaced with underscores)
        assert safe_name == "test_appgw_123"

    def test_application_gateway_includes_location(self):
        """Test that Application Gateway includes location in config."""
        emitter = TerraformEmitter()
        setup_appgw_dependencies(emitter)

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "westeurope",
            "resource_group": "test-rg",
            "properties": json.dumps(get_minimal_appgw_properties()),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify location is included
        assert config.get("location") == "westeurope"
        assert config.get("resource_group_name") == "test-rg"


class TestApplicationGatewaySkippingBehavior:
    """Test Application Gateway skipping behavior when dependencies are missing.

    Bug fix: Application Gateways should be skipped (return None) when:
    1. Subnet reference cannot be resolved
    2. Public IP reference cannot be resolved
    3. Required configuration blocks are missing

    This prevents generating invalid Terraform with placeholder references like:
    - ${azurerm_subnet.unknown_subnet.id}
    - ${azurerm_public_ip.appgw_pip.id}
    """

    def test_appgw_skipped_when_no_subnet_id(self):
        """Test that AppGW is skipped when no subnet ID is found."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "gatewayIPConfigurations": [
                    {
                        "name": "gateway-ip-config",
                        "properties": {}  # No subnet reference
                    }
                ]
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        # Should be skipped due to missing subnet
        assert result is None

    def test_appgw_skipped_when_subnet_not_in_graph(self):
        """Test that AppGW is skipped when subnet doesn't exist in graph."""
        emitter = TerraformEmitter()
        # Initialize available subnets (empty - no subnets exist)
        emitter._available_subnets = set()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "gatewayIPConfigurations": [
                    {
                        "name": "gateway-ip-config",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/appgw-subnet"
                            }
                        }
                    }
                ]
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        # Should be skipped because subnet not in _available_subnets
        assert result is None

    def test_appgw_skipped_when_no_public_ip_id(self):
        """Test that AppGW is skipped when no public IP ID is found."""
        emitter = TerraformEmitter()
        # Add subnet to available subnets so subnet check passes
        emitter._available_subnets = {"test_vnet_appgw_subnet"}

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "gatewayIPConfigurations": [
                    {
                        "name": "gateway-ip-config",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/appgw-subnet"
                            }
                        }
                    }
                ],
                "frontendIPConfigurations": [
                    {
                        "name": "frontend-ip-config",
                        "properties": {}  # No public IP reference
                    }
                ]
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        # Should be skipped due to missing public IP
        assert result is None

    def test_appgw_skipped_when_public_ip_not_in_graph(self):
        """Test that AppGW is skipped when public IP doesn't exist in graph."""
        emitter = TerraformEmitter()
        # Add subnet to available subnets
        emitter._available_subnets = {"test_vnet_appgw_subnet"}
        # Initialize available resources (no public IPs)
        emitter._available_resources = {}

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "gatewayIPConfigurations": [
                    {
                        "name": "gateway-ip-config",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/appgw-subnet"
                            }
                        }
                    }
                ],
                "frontendIPConfigurations": [
                    {
                        "name": "frontend-ip-config",
                        "properties": {
                            "publicIPAddress": {
                                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-pip"
                            }
                        }
                    }
                ]
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        # Should be skipped because public IP not in _available_resources
        assert result is None

    def test_appgw_succeeds_with_valid_dependencies(self):
        """Test that AppGW is created when all dependencies exist in graph."""
        emitter = TerraformEmitter()
        # Add subnet to available subnets
        emitter._available_subnets = {"test_vnet_appgw_subnet"}
        # Add public IP to available resources
        emitter._available_resources = {
            "azurerm_public_ip": {"test_pip"}
        }

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/applicationGateways/test-appgw",
            "name": "test-appgw",
            "type": "Microsoft.Network/applicationGateways",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "gatewayIPConfigurations": [
                    {
                        "name": "gateway-ip-config",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/appgw-subnet"
                            }
                        }
                    }
                ],
                "frontendIPConfigurations": [
                    {
                        "name": "frontend-ip-config",
                        "properties": {
                            "publicIPAddress": {
                                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-pip"
                            }
                        }
                    }
                ]
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        # Should succeed with all dependencies present
        assert result is not None
        terraform_type, safe_name, config = result

        # Verify proper references (not placeholders)
        assert config["gateway_ip_configuration"][0]["subnet_id"] == "${azurerm_subnet.test_vnet_appgw_subnet.id}"
        assert config["frontend_ip_configuration"][0]["public_ip_address_id"] == "${azurerm_public_ip.test_pip.id}"
