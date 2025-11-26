"""SSH Public Key handler for Terraform emission.

Handles: Microsoft.Compute/sshPublicKeys
Emits: azurerm_ssh_public_key
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class SSHPublicKeyHandler(ResourceHandler):
    """Handler for Azure SSH Public Keys.

    Emits:
        - azurerm_ssh_public_key
    """

    HANDLED_TYPES: ClassVar[Set[str]] = {
        "Microsoft.Compute/sshPublicKeys",
    }

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_ssh_public_key",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """Convert Azure SSH Public Key to Terraform configuration."""
        resource_name = resource.get("name", "unknown")
        safe_name = self.sanitize_name(resource_name)
        properties = self.parse_properties(resource)

        config = self.build_base_config(resource)

        # Public key (required)
        public_key = properties.get(
            "publicKey",
            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC... placeholder",
        )
        config["public_key"] = public_key

        logger.debug(f"SSH Public Key '{resource_name}' emitted")

        return "azurerm_ssh_public_key", safe_name, config
