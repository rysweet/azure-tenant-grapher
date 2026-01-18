"""Key Vault conflict handler (stub implementation).

Future Work: Implement proper Key Vault soft-delete conflict detection and resolution.
See src/iac/FUTURE_WORK.md - TODO #3 for complete implementation specifications.
This is a stub to unblock IaC generation. Real implementation needed for production.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class KeyVaultHandler:
    """Handles Key Vault naming conflicts and soft-delete state.

    STUB IMPLEMENTATION: Currently returns no conflicts.
    Real implementation should:
    - Check for soft-deleted Key Vaults in target subscription
    - Detect naming conflicts
    - Optionally purge soft-deleted vaults
    - Return name mapping for conflicts
    """

    def handle_vault_conflicts(
        self,
        vault_names: List[str],
        subscription_id: str,
        location: Optional[str] = None,
        auto_purge: bool = False,
    ) -> Dict[str, str]:
        """Check for Key Vault conflicts and optionally resolve them.

        Args:
            vault_names: List of Key Vault names to check
            subscription_id: Target Azure subscription ID
            location: Azure region for Key Vaults
            auto_purge: Whether to auto-purge soft-deleted vaults

        Returns:
            Dictionary mapping old names to new names (empty if no conflicts)
        """
        logger.warning(
            f"KeyVaultHandler.handle_vault_conflicts() is a stub. "
            f"Checked {len(vault_names)} vault names but no conflict detection implemented yet."
        )
        return {}  # No conflicts detected (stub)
