# Azure Tenant Grapher – Architecture & Enrichment Roadmap

_This document expands the previously-agreed roadmap into discrete, numbered recommendations with narrative detail, expected changes, and noted dependencies._

---

## 1. Resource-Change Tracking & Delta Ingestion
**Goal** Keep the graph continuously in sync while minimising API calls.

* **What to implement**
  * Query Azure Resource Graph’s **`resourcechanges`** table and ARM **Activity Logs** for each subscription.
  * Maintain a `LastSyncedTimestamp` per subscription; only pull changes since that point.
  * Upsert changed resources; mark deleted resources as **`state="deleted"`** (or optionally remove).
  * Optional future: Event Grid listener that pushes resource-write events to a queue for near-real-time updates.

* **Expected code changes**
  * New `ChangeFeedIngestionService` (Python) / `.NET` analogue.
  * Extend `AzureDiscoveryService` to schedule Δ runs.
  * Neo4j indices on `(Resource {id})` must exist for fast upsert.

* **Dependencies**  → Requires §7 *Graph Schema Versioning* (to evolve safely).

---

## 2. RBAC & Identity Modelling
**Goal** Represent who/what can access resources.

* **What to implement**
  * Nodes: **`RoleDefinition`**, **`RoleAssignment`**, **`User`**, **`ServicePrincipal`**, **`ManagedIdentity`**, **`IdentityGroup`**.
  * Edges:
    * `ASSIGNED_TO` (RoleAssignment → Identity)
    * `HAS_ROLE` (Identity → RoleDefinition)
    * `USES_IDENTITY` (Resource → ManagedIdentity)

* **Expected code changes**
  * Add relationship rules in `relationship_rules/identity_rule.py`.
  * Extend ARM parsing to read `identity`, `principalId`.
  * Pull MS Graph data for AAD users / groups.

* **Dependencies**  → Relies on §15 *Plugin System* to register new rules cleanly.

---

## 3. Policy & Compliance Coverage
**Goal** Expose governance posture inside the graph.

* **What to implement**
  * Nodes: **`Policy`**, **`PolicyAssignment`**, **`ComplianceResult`**.
  * Edge: `EVALUATED_AGAINST` (Resource → PolicyAssignment), `HAS_RESULT` (PolicyAssignment → ComplianceResult).
  * Track `complianceState = noncompliant|compliant`.

* **Expected code changes**
  * New `PolicyIngestionService` – calls `az policy state list` or REST equivalent.
  * Add Cypher constraints & visualizer colour mapping.

* **Dependencies**  → §10 *Enhanced Subset Filter* will use compliance predicates.

---

## 4. Network Topology Enrichment
**Goal** Model connectivity & private endpoints.

* **What to implement**
  * Nodes: **`PrivateEndpoint`**, **`DNSZone`**.
  * Edges: `CONNECTED_TO_PE` (Resource ↔ PrivateEndpoint), `RESOLVES_TO` (DNSZone → Resource).
  * Optionally infer VNET peering edges via Network Watcher topology API.

* **Expected code changes**
  * Extend `network_rule.py`; ensure idempotent creation.
  * Update 3D visualizer legends for new node types.

* **Dependencies**  → None, but complements §6 *Secrets* for defence-in-depth mapping.

---

## 5. Operational Instrumentation Nodes
**Goal** Capture monitoring & diagnostics links.

* **What to implement**
  * Nodes: **`DiagnosticSetting`**, **`AlertRule`**, **`LogAnalyticsWorkspace`** (if not already).
  * Edge: `SENDS_DIAG_TO` (Resource → DiagnosticSetting).

* **Expected code changes**
  * Parse `Microsoft.Insights/diagnosticSettings` ARM children.
  * Relationship rule to connect resources to their diagnostics sinks.

* **Dependencies**  → §14 *Batched DB Writes* (high-volume diagnostics).

---

## 6. Secrets & Key Management Representation
**Goal** Surface secret sprawl & dependencies.

* **What to implement**
  * Node: **`KeyVaultSecret`** with minimal props `{name, contentType}` (value omitted).
  * Edge: `STORES_SECRET` (KeyVault → KeyVaultSecret).

* **Expected code changes**
  * Update Azure discovery to call `SecretsClient.list_properties_of_secrets`.
  * Ensure **no secret values** are stored.

* **Dependencies**  → §12 *Async Processing* (KeyVault APIs are rate-limited).

---

## 7. Graph Schema Versioning & Migration
**Goal** Evolve Neo4j schema without breaking existing graphs.

* **What to implement**
  * Add singleton node `(GraphVersion {major, minor, appliedAt})`.
  * Each release carries migration scripts (`migrations/*.cypher`).
  * App checks version at startup and applies pending migrations.

* **Expected code changes**
  * `migration_runner.py` utility.
  * CI test runs migrations on blank DB.

* **Dependencies**  → Required for _all_ enrichment features (§1–§6).

---

## 8. Subset-Aware **GraphDiff** & Drift Detection
**Goal** Compare target subset to live tenant for safe re-deploy.

* **What to implement**
  * `GraphDiff` component: compute **added / changed / removed** nodes & edges.
  * Export diff as Markdown summary and feed to IaC generator to emit only required ops.

* **Expected code changes**
  * Extend `iac/engine.py` to accept a `graph_diff` object.
  * CLI flag `--what-if` prints coloured diff.

* **Dependencies**  → §11 *Continuous IaC Validation*.

---

## 9. Parameterisation & IaC Schema Awareness
**Goal** Allow reusable templates across environments.

* **What to implement**
  * Three levels: **inline literals**, **Bicep/TF variables**, or **parameter files**.
  * Emitters consult provider JSON (Bicep `types/*.json`, Terraform `providers schema`) to know required props.

* **Expected code changes**
  * Enhance `bicep_emitter.py` / `terraform_emitter.py`.
  * New `SchemaInspector` helper.

* **Dependencies**  → §8 because diff determines which params may change.

---

## 10. Enhanced Subset Filter & Closure Policies
**Goal** Powerful graph slicing.

* **What to implement**
  * New predicates: `policyState`, `createdAfter`, `tagSelector`, `depth=N`.
  * **Closure** rules to auto-include parent scopes, diagnostics, role assignments.

* **Expected code changes**
  * Extend `SubsetFilter` dataclass and `subset.py`.
  * Unit tests at `tests/iac/test_subset_selector.py`.

* **Dependencies**  → §3 compliance nodes, §2 RBAC edges.

---

## 11. Continuous IaC Validation Pipeline
**Goal** Fail fast on template errors & drift.

* **What to implement**
  * GitHub Actions step:
    ```bash
    az bicep build --file main.bicep
    az deployment what-if -f main.bicep -l eastus --no-pretty-print
    ```
  * Parse what-if JSON; fail if unexpected deletes/renames.

* **Expected code changes**
  * `.github/workflows/iac.yml`.
  * Python helper to annotate PR with diff.

* **Dependencies**  → §9 emitter upgrades.

---

## 12. Async Resource Processing & Concurrency Control
**Goal** Increase throughput while avoiding thread-safety bugs.

* **What to implement**
  * Replace `ThreadPoolExecutor` with **`asyncio`** + **`aiohttp`** for ARM REST.
  * Use `asyncio.Semaphore` to bound concurrent calls.

* **Expected code changes**
  * Rewrite `AzureDiscoveryService.discover_*` methods.
  * Add `AsyncNeo4jSession` wrapper (Neo4j driver supports async).

* **Dependencies**  → §14 batched writes for optimal perf.

---

## 13. Failure Isolation & Retry Queues
**Goal** Prevent one bad resource blocking the run.

* **What to implement**
  * In-memory retry queue with exponential back-off.
  * After N failures, move to **poison list** and continue.

* **Expected code changes**
  * Update `ResourceProcessingService` main loop.
  * Expose CLI `--max-retries` flag.

* **Dependencies**  → §12 async architecture.

---

## 14. Batched Database Writes & Transactions
**Goal** Reduce Neo4j latency and contention.

* **What to implement**
  * Collect up to 1000 `MERGE`/`CREATE` rows and write via
    ```cypher
    UNWIND $batch AS r
    CALL { ... } IN TRANSACTIONS OF 1000 ROWS
    ```
  * Use Neo4j **`apoc.periodic.iterate`** for backfill scripts.

* **Expected code changes**
  * Enhance `DatabaseOperations` with batch buffer & flush timer.
  * Update stats tracking.

* **Dependencies**  → §12 async loop for timely flush.

---

## 15. Plugin System for Relationship Rules
**Goal** Enable third-party or out-of-tree enrichments.

* **What to implement**
  * Publish an **`entry_points`** group `azure_tenant_grapher.relationship_rules`.
  * At runtime, discover and register rule classes.

* **Expected code changes**
  * Modify `relationship_rules/__init__.py` to iterate `importlib.metadata.entry_points`.

* **Dependencies**  → Supports §2–§6 new rule modules.

---

## 16. Golden Graph Fixtures & Cross-Language Parity
**Goal** Guarantee .NET & Python implementations behave identically.

* **What to implement**
  * YAML/JSON snapshot of a mini tenant (≈ 15 resources).
  * Used by tests in both repos to assert node/edge counts.

* **Expected code changes**
  * Add `tests/fixtures/golden_graph.json`.
  * Adapter classes in C# tests to load snapshot.

* **Dependencies**  → Eases validation of §1–§6 enrichments.

---

## 17. Contract Tests & Schema Drift Guards
**Goal** Detect silent breaking changes early.

* **What to implement**
  * For each `RelationshipRule`, feed minimal ARM stub ➜ assert generated Cypher via mocks.
  * Nightly job runs `CALL db.schema.visualization()` and compares to committed JSON.

* **Expected code changes**
  * Add `tests/contract/` suite.
  * JSON schema diff helper.

* **Dependencies**  → Relies on §7 versioning.

---

## 18. CI Matrix & Environment Coverage
**Goal** Ensure compatibility across runtimes.

* **What to implement**
  * GitHub Actions matrix: Python 3.8-3.12 and .NET 8.
  * Integration job spins up Neo4j via `docker-compose`.

* **Expected code changes**
  * Update `.github/workflows/ci.yml`.

* **Dependencies**  → Foundation for all dev work; no vertical dependencies.

---

### Removed Recommendation

*The earlier suggestion to “enforce boundaries with **mypy**” has been **dropped** because the project does not use mypy. Type safety can be revisited later if desired.*

---
## Appendix: Migration Infrastructure & Versioning

### Migration Infrastructure

- All schema changes are managed via versioned Cypher migration scripts in [`migrations/`](../migrations/).
- The migration runner ([`src/migration_runner.py`](../src/migration_runner.py), invoked by [`scripts/run_migrations.py`](../scripts/run_migrations.py)) applies all pending migrations to the Neo4j database.
- Migrations are tracked by a singleton `GraphVersion` node with `major`, `minor`, and `appliedAt` properties.

### Schema Constraints

- Uniqueness constraints are enforced for all core node types (Resource, ResourceGroup, Tag, Region, User, ServicePrincipal, ManagedIdentity, LogAnalyticsWorkspace, Subscription).
- See [`migrations/0002_add_core_constraints.cypher`](../migrations/0002_add_core_constraints.cypher) for details.

### Migration Files & Purposes

- [`0001_create_graph_version.cypher`](../migrations/0001_create_graph_version.cypher): Creates the `GraphVersion` node and uniqueness constraint.
- [`0002_add_core_constraints.cypher`](../migrations/0002_add_core_constraints.cypher): Adds uniqueness constraints and indexes for all core node types.
- [`0003_backfill_subscriptions.cypher`](../migrations/0003_backfill_subscriptions.cypher): Adds `Subscription` nodes, `CONTAINS` relationships, and backfills `subscription_id` fields.

### Adding New Migrations

1. Create a new Cypher script in `migrations/` with the next available sequence number (e.g., `0004_new_feature.cypher`).
2. Write idempotent Cypher statements for the schema/data change.
3. The migration will be auto-applied by the runner if its sequence is higher than the current `GraphVersion`.
4. Document the migration's purpose in this section.

### CI Integration

- The CI workflow spins up a Neo4j container, runs all migrations using the migration runner, and verifies that all migrations apply cleanly on a blank database.

---

## Dependency Graph

```mermaid
graph TD
  A1(Resource-Change) --> S7(GraphVersion)
  A2(RBAC) --> P15(Plugin)
  A3(Policy) --> S10(Subsets)
  A4(Network) -->
  A5(Ops) -->
  A6(Secrets) --> S12(Async)
  S12(Async) --> S14(BatchedWrites)
  S12 --> F13(RetryQueues)
  S14 --> |
  S7 --> C17(ContractTests)
  S10(Subsets) --> V11(IaCValidation)
  D8(GraphDiff) --> V11
```

*(Edges show a “depends on” relationship.)*

---

## Next Steps

1. Track each section (§1–§18) as a **GitHub Issue** labelled `feature` & `added by o3`.
2. Implement migrations for §7 before shipping any new enrichments.
3. Triage & queue work in iterative milestones.
