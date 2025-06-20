# Azure Tenant Grapher: Graph Enrichment & Refactor Plan

## 1. Current Model

- **Nodes:** Tenant, Subscription, ResourceGroup, Resource
- **Edges:** CONTAINS (Subscription→ResourceGroup, ResourceGroup→Resource, Subscription→Resource), plus a handful of hard-coded non-containment edges (DEPENDS_ON, USES_SUBNET, etc.)
- **Limitations:** No first-class nodes for Tags, Region, Identities, KeyVault secrets, etc. Relationship rules are scattered and not modular/testable.

---

## 2. Proposed Enrichment

### New Node Types
- **Tag** (`Tag`): `{key, value}`
- **Region** (`Region`): `{name, code}`
- **User/ServicePrincipal** (`User`, `ServicePrincipal`)
- **ManagedIdentity** (`ManagedIdentity`)
- **IdentityGroup** (`IdentityGroup`)
- **RoleDefinition** (`RoleDefinition`)
- **RoleAssignment** (`RoleAssignment`)
- **KeyVaultSecret** (`KeyVaultSecret`)
- **DiagnosticSetting** (`DiagnosticSetting`)
- **PrivateEndpoint** (`PrivateEndpoint`)

### New Edge Types
- `TAGGED_WITH` (Resource→Tag)
- `LOCATED_IN` (Resource→Region)
- `CREATED_BY` (Resource→User/ServicePrincipal)
- `USES_IDENTITY` (Resource→ManagedIdentity)
- `HAS_ROLE` (Identity→RoleDefinition)
- `ASSIGNED_TO` (RoleAssignment→Identity)
- `INHERITS_TAG` (ResourceGroup/Subscription→Tag)
- `STORES_SECRET` (KeyVault→KeyVaultSecret)
- `SENDS_DIAG_TO` (Resource→DiagnosticSetting)
- `CONNECTED_TO_PE` (Resource↔PrivateEndpoint)

---

## 3. Refactor Architecture

- **relationship_rules/**: Each file defines a `RelationshipRule` subclass (e.g., `TagRule`, `RegionRule`, `CreatorRule`, etc.), all registered in a list in `ResourceProcessor`.
- **db_ops.py**: Pure data-access layer for all node/edge creation.
- **resource_normalizer.py**: Functions to normalize ARM resource dicts (e.g., expand `identity`, surface `createdBy`).
- **resource_processor.py**: Handles threading/stats, delegates enrichment to a `RelationshipEngine` that loops over rules.

**Example:**
```python
# relationship_rules/region_rule.py
class RegionRule(RelationshipRule):
    def applies(self, r: dict) -> bool:
        return bool(r.get("location"))
    def emit(self, r: dict, db: DatabaseOperations) -> None:
        region = r["location"].lower()
        db.upsert_generic("Region", "code", region, {"name": region})
        db.create_generic_rel(r["id"], "LOCATED_IN", region, "Region", "code")
```
---

## 4. Test Strategy

- **Unit tests** per rule: Feed minimal resource dict, assert Neo4j queries executed via mock session.
- **Integration test**: Ingest fixture ARM JSON, assert node/edge counts.
- **Contract test**: Ensure adding a new rule doesn’t break stats schema.

---

## 5. Migration & Compatibility

- Introduce rules engine in parallel with existing `_create_enriched_relationships`; after parity, remove old method.
- Backfill existing DB: run a one-off script to create Region & Tag nodes for existing resources.
- Update `graph_visualizer` to include new node types.
- Update anonymizer in `tenant_spec_generator` to treat Tag/Region.

---

## 6. Work Breakdown

| Phase | Effort | Deliverable |
|-------|--------|-------------|
| 1     | 0.5 d  | Folder `relationship_rules`, base `interface`, migrate existing network & identity logic into rules |
| 2     | 0.5 d  | TagRule, RegionRule, CreatorRule; unit tests |
| 3     | 0.5 d  | Schema change Cypher for Tag/Region nodes & relationships; migration script |
| 4     | 0.5 d  | Visualizer color/group map update; docs & README |
| 5     | 0.5 d  | Refactor `_create_enriched_relationships` callers, remove legacy code, update tests |

Total ≈ 2–3 developer-days.

---

## 7. Documentation/Requirements Updates

- **README.md**: Add new node/edge types, describe rules engine, update architecture diagram.
- **.github/azure-tenant-grapher-prd.md**: Add requirements for tag/region/creator enrichment, modularity, and testability.
- **.github/azure-tenant-grapher-spec.md**: Update design to reflect new extensible relationship engine and node/edge vocabulary.

---

## 8. Next Steps

1. Implement `relationship_rules/` and migrate existing logic.
2. Add Tag, Region, and Creator rules.
3. Update documentation and requirements as above.
4. Backfill/migrate existing data if needed.
5. Remove legacy enrichment logic after validation.
