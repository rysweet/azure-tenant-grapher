# Dual-Graph Architecture Documentation Index

## Quick Navigation

This index provides quick access to all dual-graph architecture documentation.

## Core Design Documents

### 1. Dual-Graph Design Overview
**Start here!** High-level overview and quick reference.

See [architecture/dual-graph.md](architecture/dual-graph.md) for details on:
- What is dual-graph architecture
- Key design decisions
- Node and relationship schemas
- Quick query patterns
- Implementation approach

---

### 2. [DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md)
**Complete schema specification.** Authoritative reference for database design.

**Contains:**
- Detailed node label strategy (10 pages)
- Complete property schemas
- All relationship types
- Indexes and constraints
- Migration strategy
- Query patterns with 40+ examples
- Schema issues and solutions
- Implementation checklist

**Best for:**
- Database administrators
- Backend developers
- Schema design reviews
- Migration planning

---

### 3. [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher)
**Query cookbook.** 100+ Cypher query examples.

**Contains:**
- Basic queries (get resources)
- Cross-reference queries (original ↔ abstracted)
- Topology queries (graph structure)
- Comparison queries (find differences)
- Validation queries (data quality)
- IaC generation queries
- Debugging queries
- Performance testing queries
- Advanced analysis queries

**Best for:**
- Database operators
- Query optimization
- Troubleshooting
- Writing new features
- Copy-paste reference

---

### 4. [DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py)
**Code reference.** Python implementation patterns.

**Contains:**
- `AbstractionIDGenerator` class
- `DualGraphDatabaseOperations` class
- `TenantSeedManager` class
- Relationship rule examples
- Usage examples
- Integration notes
- 500+ lines of documented code

**Best for:**
- Backend developers
- Code reviews
- Implementation reference
- Understanding the code structure

---

### 5. Implementation Reference
**Project plan.** Implementation is complete.

For current implementation details, see the source code in `src/` directory and the complete schema in DUAL_GRAPH_SCHEMA.md.

---

### 6. [DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt](./DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt)
**Visual reference.** ASCII diagrams of the architecture.

**Contains:**
- High-level architecture diagram
- Node structure comparison
- Relationship duplication visualization
- ID generation flow
- Query flow diagrams
- Data flow diagrams
- Complete examples

**Best for:**
- Visual learners
- Documentation
- Presentations
- Onboarding new team members

---

## Database Migration

### 7. [../migrations/0010_dual_graph_schema.cypher](../migrations/0010_dual_graph_schema.cypher)
**Database migration script.** Actual Cypher migration.

**Contains:**
- Constraint definitions
- Index definitions
- Migration of existing data (optional)
- Verification queries
- Rollback notes

**Best for:**
- Database administrators
- DevOps engineers
- Production deployment

---

## Quick Reference by Role

### For Backend Developers

**Start here:**
2. [DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py) - See code patterns (30 min)
3. [DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md) - Understand schema (1 hour)
4. [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher) - Query reference (ongoing)

**Key sections:**
- Implementation Approach (Summary)
- Code Changes Required (Summary)
- Database Operations (Example)
- Relationship Rules (Example)
- Node Label Strategy (Schema)
- Query Patterns (Schema & Queries)

---

### For Database Administrators

**Start here:**
2. [DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md) - Complete schema spec (1 hour)
3. [../migrations/0010_dual_graph_schema.cypher](../migrations/0010_dual_graph_schema.cypher) - Migration script (15 min)
4. [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher) - Validation queries (30 min)

**Key sections:**
- Indexes and Constraints (Schema)
- Migration Strategy (Schema)
- Validation Queries (Queries)
- Administrative Queries (Queries)
- Performance Testing (Queries)

---

### For Project Managers

**Start here:**
3. [DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt](./DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt) - Visual reference (15 min)

**Key sections:**
- Timeline Summary (Strategy)
- Phase-Based Rollout (Strategy)
- Risk Mitigation (Strategy)
- Success Criteria (Strategy & Summary)
- Stakeholder Communication (Strategy)

---

### For DevOps Engineers

**Start here:**
2. [../migrations/0010_dual_graph_schema.cypher](../migrations/0010_dual_graph_schema.cypher) - Migration script (15 min)
4. [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher) - Monitoring queries (30 min)

**Key sections:**
- Feature Flag (Summary & Strategy)
- Rollback Plan (Strategy & Summary)
- Production Deployment (Strategy)
- Validation Queries (Queries)
- Monitoring (Strategy)

---

### For New Team Members

**Start here:**
1. [DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt](./DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt) - Visual overview (15 min)
3. [DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py) - Code walkthrough (1 hour)

**Learning path:**
- Read diagram for visual understanding
- Read summary for design decisions
- Study code example for implementation
- Reference schema and queries as needed

---

## Quick Reference by Task

### Planning Implementation

**Documents:**

**Sections:**
- Implementation Phases (Strategy)
- Timeline Summary (Strategy)
- Testing Strategy (Strategy)

---

### Writing Code

**Documents:**
- [DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py) - Code patterns
- [DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md) - Schema reference

**Sections:**
- Abstraction Service (Example)
- Database Operations (Example)
- Relationship Rules (Example)
- Node Schema (Schema)

---

### Writing Queries

**Documents:**
- [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher) - Query cookbook
- [DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md) - Schema reference

**Sections:**
- All query sections (Queries)
- Query Patterns (Schema)

---

### Deploying to Production

**Documents:**
- [../migrations/0010_dual_graph_schema.cypher](../migrations/0010_dual_graph_schema.cypher) - Migration

**Sections:**
- Staging and Production Rollout (Strategy)
- Rollback Plan (Strategy)
- Migration Strategy (Schema)

---

### Troubleshooting Issues

**Documents:**
- [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher) - Debugging queries
- [DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md) - Schema issues

**Sections:**
- Validation Queries (Queries)
- Debugging Queries (Queries)
- Potential Schema Issues (Schema)

---

## Document Sizes

For planning reading time:

| Document | Lines | Read Time | Type |
|----------|-------|-----------|------|
| DUAL_GRAPH_SCHEMA.md | ~1,200 | 60 min | Comprehensive spec |
| DUAL_GRAPH_QUERIES.cypher | ~700 | 30 min | Query cookbook |
| DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py | ~600 | 45 min | Code reference |
| DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt | ~500 | 20 min | Visual reference |
| 0010_dual_graph_schema.cypher | ~120 | 10 min | Migration script |

**Total reading time**: ~4.5 hours for complete understanding

---

## Key Concepts

Quick reference to key concepts mentioned across documents:

### Abstracted Node
- Node with hash-based ID (e.g., `vm-a1b2c3d4`)
- Used for IaC generation
- Has `:Resource:Abstracted` labels
- See: Summary (section 2), Schema (section 2.1), Diagram (section 2)

### Original Node
- Node with Azure resource ID
- Preserves exact Azure topology
- Has `:Resource:Original` labels
- See: Summary (section 2), Schema (section 2.2), Diagram (section 2)

### SCAN_SOURCE_NODE
- Relationship linking abstracted to original
- Direction: `(Abstracted)-[:SCAN_SOURCE_NODE]->(Original)`
- See: Summary (section 2), Schema (section 3.1), Diagram (section 2)

### Abstraction ID
- Deterministic hash ID (type-prefix-hash)
- Generated from Azure ID + tenant seed
- See: Summary (section 2), Schema (section 2.1), Example (section 1), Diagram (section 4)

### Tenant Seed
- Per-tenant random seed for ID generation
- Stored on Tenant node
- Ensures consistency within tenant
- See: Summary (section 2), Schema (section 2.4), Example (section 3), Diagram (section 5)

### Dual Graph
- Two parallel graphs (Original + Abstracted)
- Same topology, different IDs
- See: Summary (intro), Diagram (section 1, 3)

### Feature Flag
- `ENABLE_DUAL_GRAPH` environment variable
- Allows gradual rollout
- Easy rollback mechanism
- See: Summary (section 5), Strategy (all phases), Diagram (section 10)

---

## Cheat Sheet

### Most Common Queries

```cypher
-- Get all abstracted resources
MATCH (r:Resource:Abstracted) WHERE r.tenant_id = $tenant_id RETURN r;

-- Get original source for abstracted
MATCH (abs:Abstracted {id: $id})-[:SCAN_SOURCE_NODE]->(orig:Original) RETURN orig;

-- Find orphaned nodes
MATCH (abs:Abstracted) WHERE NOT (abs)-[:SCAN_SOURCE_NODE]->() RETURN abs;

-- Check relationship parity
MATCH (orig:Original)-[r]->() WITH count(r) as orig_count
MATCH (abs:Abstracted)-[r]->() WITH orig_count, count(r) as abs_count
RETURN orig_count, abs_count, orig_count - abs_count as diff;
```

See: [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher) for 100+ more

### Most Common Code Patterns

```python
# Generate abstracted ID
generator = AbstractionIDGenerator(tenant_seed)
abstracted_id = generator.generate_id(resource)

# Create dual-graph resource
db_ops.upsert_dual_graph_resource(resource)

# Create dual-graph relationship
db_ops.create_dual_graph_rel(src_id, rel_type, tgt_id)
```

See: [DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py) for complete examples

---

## Getting Help

### Common Questions

**Q: How do I query for IaC generation?**
A: See [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher) section 6

**Q: How do I implement a relationship rule?**
A: See [DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py) section 4

**Q: What indexes do I need?**
A: See [DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md) section 4

**Q: How do I rollback?**

**Q: How do I detect orphaned nodes?**
A: See [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher) section 5

---

## Document Change Log

| Date | Document | Changes |
|------|----------|---------|
| 2025-11-05 | All | Initial creation |

---

## Next Steps

3. **Need a specific query?** Search [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher)
4. **Writing code?** Reference [DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py)
5. **Confused?** Look at [DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt](./DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt)

---

**Last Updated**: 2025-11-05
**Status**: Complete - Ready for Implementation
