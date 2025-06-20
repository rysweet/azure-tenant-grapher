from typing import Any, Dict

from .relationship_rule import RelationshipRule


class RegionRule(RelationshipRule):
    """
    Emits region-related relationships:
    - (Resource) -[:LOCATED_IN]-> (Region)
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        return bool(resource.get("location"))

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        region = resource.get("location")
        if not (rid and region):
            return
        region_code = region.lower()
        db_ops.upsert_generic("Region", "code", region_code, {"name": region})
        db_ops.create_generic_rel(str(rid), "LOCATED_IN", region_code, "Region", "code")
