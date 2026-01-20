"""DevTest Lab Policy handler for Terraform emission.

Handles: Microsoft.DevTestLab/labs/policysets/policies
Emits: azurerm_dev_test_policy
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class DevTestPolicyHandler(ResourceHandler):
    """Handler for Azure DevTest Lab Policies.

    Emits:
        - azurerm_dev_test_policy
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.DevTestLab/labs/policysets/policies",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_dev_test_policy",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert DevTest Lab Policy to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        properties = self.parse_properties(resource)

        # Extract lab, policy set, and policy names
        # Format: lab/policyset/policy (e.g., "mylab/default/LabVmCount")
        parts = resource_name.split("/")
        if len(parts) >= 3:
            lab_name = parts[0]
            policy_set_name = parts[1]
            policy_name = parts[2]
        elif len(parts) == 2:
            lab_name = parts[0]
            policy_set_name = "default"
            policy_name = parts[1]
        else:
            lab_name = "unknown-lab"
            policy_set_name = "default"
            policy_name = resource_name

        safe_name = self.sanitize_name(policy_name)

        config = self.build_base_config(resource)
        config["name"] = policy_name

        # Policy properties
        fact_data = properties.get("factData", "")
        threshold = properties.get("threshold", "0")
        evaluator_type = properties.get("evaluatorType", "MaxValuePolicy")
        description = properties.get("description", "")

        config.update(
            {
                "lab_name": lab_name,
                "policy_set_name": policy_set_name,
                "fact_data": fact_data,
                "threshold": threshold,
                "evaluator_type": evaluator_type,
            }
        )

        # Add description if present
        if description:
            config["description"] = description

        logger.debug(
            f"DevTest Policy '{policy_name}' emitted for lab '{lab_name}' in policy set '{policy_set_name}'"
        )

        return "azurerm_dev_test_policy", safe_name, config
