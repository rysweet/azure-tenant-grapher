from typing import Any, Dict

from .relationship_rule import RelationshipRule


class DependsOnRule(RelationshipRule):
    """
    Emits ARM dependency relationships:
    - (Resource) -[:DEPENDS_ON]-> (target Resource)

    Supports dual-graph architecture - creates relationships in both original and abstracted graphs.
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        depends_on = resource.get("dependsOn")
        return isinstance(depends_on, list) and len(depends_on) > 0

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        depends_on = resource.get("dependsOn", [])
        for dep_id in depends_on:
            if isinstance(dep_id, str) and rid:
                # Use dual-graph helper for Resource-to-Resource relationships
                self.create_dual_graph_relationship(
                    db_ops, str(rid), "DEPENDS_ON", str(dep_id)
                )
