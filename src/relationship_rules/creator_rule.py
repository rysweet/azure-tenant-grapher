from typing import Any, Dict

from .relationship_rule import RelationshipRule


class CreatorRule(RelationshipRule):
    """
    Emits created-by relationships:
    - (Resource) -[:CREATED_BY]-> (User/ServicePrincipal)

    Supports dual-graph architecture - creates relationships in both original and abstracted graphs.
    Note: User/ServicePrincipal nodes are shared between graphs (not duplicated).
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        # ARM resources may have 'createdBy' in properties or systemData
        sysdata = resource.get("systemData", {})
        props = resource.get("properties", {})
        return bool(sysdata.get("createdBy") or props.get("createdBy"))

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        sysdata = resource.get("systemData", {})
        props = resource.get("properties", {})
        created_by = sysdata.get("createdBy") or props.get("createdBy")
        if not (rid and created_by):
            return
        # Upsert User/ServicePrincipal node (shared between graphs)
        db_ops.upsert_generic("User", "id", created_by, {"id": created_by})
        # Create relationship using dual-graph helper
        self.create_dual_graph_generic_rel(
            db_ops, str(rid), "CREATED_BY", created_by, "User", "id"
        )
