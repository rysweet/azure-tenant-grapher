"""WAF Policy handler for Terraform emission.

Handles: Microsoft.Network/frontDoorWebApplicationFirewallPolicies,
         Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies
Emits: azurerm_frontdoor_firewall_policy, azurerm_web_application_firewall_policy
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class WAFPolicyHandler(ResourceHandler):
    """Handler for Azure WAF Policies.

    Handles both Front Door and Application Gateway WAF policies.

    Emits:
        - azurerm_frontdoor_firewall_policy (for Front Door)
        - azurerm_web_application_firewall_policy (for App Gateway)
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "microsoft.network/frontdoorwebapplicationfirewallpolicies",
        "microsoft.network/applicationgatewaywebapplicationfirewallpolicies",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_frontdoor_firewall_policy",
        "azurerm_web_application_firewall_policy",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert WAF Policy to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)
        azure_type = resource.get("type", "").lower()

        config = self.build_base_config(resource)

        # Determine if Front Door or App Gateway
        is_frontdoor = "frontdoor" in azure_type

        if is_frontdoor:
            terraform_type = "azurerm_frontdoor_firewall_policy"
            config["enabled"] = (
                properties.get("policySettings", {}).get("enabledState", "Enabled")
                == "Enabled"
            )
            config["mode"] = properties.get("policySettings", {}).get(
                "mode", "Prevention"
            )
        else:
            terraform_type = "azurerm_web_application_firewall_policy"
            # Policy settings
            policy_settings = properties.get("policySettings", {})
            config["policy_settings"] = {
                "enabled": policy_settings.get("state", "Enabled") == "Enabled",
                "mode": policy_settings.get("mode", "Prevention"),
                "request_body_check": policy_settings.get("requestBodyCheck", True),
                "max_request_body_size_in_kb": policy_settings.get(
                    "maxRequestBodySizeInKb", 128
                ),
                "file_upload_limit_in_mb": policy_settings.get(
                    "fileUploadLimitInMb", 100
                ),
            }

        # Managed rules (common)
        managed_rules = properties.get("managedRules", {})
        if managed_rules.get("managedRuleSets"):
            rule_sets = []
            for rule_set in managed_rules.get("managedRuleSets", []):
                rule_sets.append(
                    {
                        "type": rule_set.get("ruleSetType", "OWASP"),
                        "version": rule_set.get("ruleSetVersion", "3.2"),
                    }
                )
            if is_frontdoor:
                config["managed_rule"] = rule_sets
            else:
                config["managed_rules"] = {"managed_rule_set": rule_sets}

        # Custom rules
        custom_rules = properties.get("customRules", {}).get("rules", [])
        if custom_rules:
            tf_custom_rules = []
            for rule in custom_rules:
                tf_rule = {
                    "name": rule.get("name", "rule"),
                    "priority": rule.get("priority", 1),
                    "rule_type": rule.get("ruleType", "MatchRule"),
                    "action": rule.get("action", "Block"),
                }
                # Match conditions
                match_conditions = rule.get("matchConditions", [])
                if match_conditions:
                    tf_matches = []
                    for match in match_conditions:
                        tf_matches.append(
                            {
                                "match_variable": match.get(
                                    "matchVariable", "RequestUri"
                                ),
                                "operator": match.get("operator", "Contains"),
                                "match_values": match.get("matchValue", []),
                            }
                        )
                    tf_rule["match_condition"] = tf_matches
                tf_custom_rules.append(tf_rule)
            config["custom_rule"] = tf_custom_rules

        logger.debug(f"WAF Policy '{resource_name}' emitted as {terraform_type}")

        return terraform_type, safe_name, config
