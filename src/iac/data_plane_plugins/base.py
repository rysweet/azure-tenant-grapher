"""
Base class for data plane replication plugins.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class DataPlanePlugin(ABC):
    """Base class for data plane replication plugins."""

    @abstractmethod
    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """Check if this plugin can handle the given resource."""
        pass

    @abstractmethod
    def replicate(self, resource: Dict[str, Any], target_resource_id: str) -> bool:
        """Replicate data plane for the resource."""
        pass
