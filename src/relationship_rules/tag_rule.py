from typing import Any, Dict

from .relationship_rule import RelationshipRule


class TagRule(RelationshipRule):
    """
    Emits tag-related relationships:
    - (Resource) -[:TAGGED_WITH]-> (Tag)
    - (ResourceGroup/Subscription) -[:INHERITS_TAG]-> (Tag)
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
            db_ops.upsert_generic("Tag", "id", tag_id, {
                "key": k,
                "value": v,
                "llm_description": ""  # Initialize empty, will be filled later
            })
            # Resource → Tag
            if rid:
                db_ops.create_generic_rel(str(rid), "TAGGED_WITH", tag_id, "Tag", "id")
            # Inheritance for ResourceGroup/Subscription
            if rtype.endswith("resourceGroups") or rtype.endswith("subscriptions"):
                db_ops.create_generic_rel(str(rid), "INHERITS_TAG", tag_id, "Tag", "id")
