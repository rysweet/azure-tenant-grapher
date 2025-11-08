from typing import Any, Dict

from .relationship_rule import RelationshipRule


class RegionRule(RelationshipRule):
    """
    Emits region-related relationships:
    - (Resource) -[:LOCATED_IN]-> (Region)

    Supports dual-graph architecture - creates relationships in both original and abstracted graphs.
    Note: Region nodes are shared between graphs (not duplicated).
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        return bool(resource.get("location"))

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        region = resource.get("location")
        if not (rid and region):
            return
        region_code = region.lower()
        # Upsert Region node (shared between graphs)
        db_ops.upsert_generic("Region", "code", region_code, {"name": region})
        # Create relationship using dual-graph helper
        self.create_dual_graph_generic_rel(
            db_ops, str(rid), "LOCATED_IN", region_code, "Region", "code"
        )
