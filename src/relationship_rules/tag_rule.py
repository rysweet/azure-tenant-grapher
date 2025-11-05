from typing import Any, Dict

from .relationship_rule import RelationshipRule


class TagRule(RelationshipRule):
    """
    Emits tag-related relationships:
    - (Resource) -[:TAGGED_WITH]-> (Tag)
    - (ResourceGroup/Subscription) -[:INHERITS_TAG]-> (Tag)

    Supports dual-graph architecture - creates relationships in both original and abstracted graphs.
    Note: Tag nodes are shared between graphs (not duplicated).
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        return bool(resource.get("tags"))

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        tags = resource.get("tags", {})
        rtype = resource.get("type", "")

        for k, v in tags.items():
            tag_id = f"{k}:{v}"
            # Upsert Tag node with llm_description field
            db_ops.upsert_generic(
                "Tag",
                "id",
                tag_id,
                {
                    "key": k,
                    "value": v,
                    "llm_description": "",  # Initialize empty, will be filled later
                },
            )
            # Resource → Tag (use dual-graph helper)
            if rid:
                self.create_dual_graph_generic_rel(
                    db_ops, str(rid), "TAGGED_WITH", tag_id, "Tag", "id"
                )
            # Inheritance for ResourceGroup/Subscription (use dual-graph helper)
            if rtype.endswith("resourceGroups") or rtype.endswith("subscriptions"):
                self.create_dual_graph_generic_rel(
                    db_ops, str(rid), "INHERITS_TAG", tag_id, "Tag", "id"
                )
