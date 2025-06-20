from abc import ABC, abstractmethod
from typing import Any, Dict


class RelationshipRule(ABC):
    """
    Abstract base class for all relationship enrichment rules.
    Each rule determines if it applies to a resource and emits relationships via db_ops.
    """

    @abstractmethod
    def applies(self, resource: Dict[str, Any]) -> bool:
        """Return True if this rule should process the given resource."""
        pass

    @abstractmethod
    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        """
        Emit any nodes/edges for this resource using db_ops.
        db_ops: DatabaseOperations instance.
        """
        pass
