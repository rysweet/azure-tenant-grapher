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

        # Ensure sysdata and props are dictionaries
        if not isinstance(sysdata, dict):
            sysdata = {}
        if not isinstance(props, dict):
            props = {}

        return bool(sysdata.get("createdBy") or props.get("createdBy"))

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        sysdata = resource.get("systemData", {})
        props = resource.get("properties", {})

        # Ensure sysdata and props are dictionaries
        if not isinstance(sysdata, dict):
            sysdata = {}
        if not isinstance(props, dict):
            props = {}

        created_by = sysdata.get("createdBy") or props.get("createdBy")
        if not (rid and created_by):
            return

        # Handle case where created_by might be a string instead of a dict
        if isinstance(created_by, str):
            creator_id = created_by
        elif isinstance(created_by, dict):
            # Extract ID from the dictionary (common Azure format)
            creator_id = (
                created_by.get("id")
                or created_by.get("objectId")
                or created_by.get("principalId")
            )
        else:
            return  # Unknown format, skip

        if not creator_id:
            return

        # Upsert User/ServicePrincipal node (shared between graphs)
        db_ops.upsert_generic("User", "id", creator_id, {"id": creator_id})
        # Create relationship using dual-graph helper
        self.create_dual_graph_generic_rel(
            db_ops, str(rid), "CREATED_BY", creator_id, "User", "id"
        )
