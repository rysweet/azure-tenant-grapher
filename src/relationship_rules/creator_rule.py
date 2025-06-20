from typing import Any, Dict

from .relationship_rule import RelationshipRule


class CreatorRule(RelationshipRule):
    """
    Emits created-by relationships:
    - (Resource) -[:CREATED_BY]-> (User/ServicePrincipal)
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
        # Upsert User/ServicePrincipal node (type detection could be improved)
        db_ops.upsert_generic("User", "id", created_by, {"id": created_by})
        db_ops.create_generic_rel(str(rid), "CREATED_BY", created_by, "User", "id")
