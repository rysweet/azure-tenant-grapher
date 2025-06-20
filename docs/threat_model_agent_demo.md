# Threat Modeling Agent Demo

This demo illustrates the end-to-end workflow of the Threat Modeling Agent using the current Neo4j graph.

## Step 1: Build the Azure Graph

```bash
azure-tenant-grapher build --tenant-id XXXX-XXXX-XXXX-XXXX --no-dashboard
```

**Sample Output:**
```
🎉 Graph building completed.
Result: {'total_resources': 10, 'processed': 10, 'successful': 1, 'failed': 0, 'skipped': 9, 'llm_generated': 1, 'llm_skipped': 9, 'success_rate': 10.0, 'progress_percentage': 100.0, 'subscriptions': 1, 'success': True}
```

## Step 2: Run the Threat Modeling Agent

```bash
azure-tenant-grapher threat-model
```

**Actual Output:**
```
🚀 Starting Threat Modeling Agent workflow...
Waiting for Neo4j to be ready...
Neo4j is ready!
=== Threat Modeling Agent: Starting workflow ===
[Stage] Building DFD (Data Flow Diagram)...
✅ DFD artifact (Mermaid diagram):
flowchart TD
    /subscriptions/XXXX-XXXX-XXXX-XXXX/resourceGroups/XXXX/providers/Microsoft.Network/networkInterfaces/aaXXXX["/subscriptions/XXXX-XXXX-XXXX-XXXX/resourceGroups/XXXX/providers/Microsoft.Network/networkInterfaces/aaXXXX"]
    ... (many more nodes and edges, all IDs obfuscated) ...
[Stage] Invoking Microsoft Threat Modeling Tool (TMT)...
TMT runner returned no threats.
⚠️  TMT runner returned no threats.
=== Threat Modeling Agent: Workflow complete ===
✅ Threat Modeling Agent workflow complete.
```

## Step 3: View the Mermaid DFD

Open the generated Mermaid diagram in a Mermaid live editor or compatible tool.

**Extract:**
```
flowchart TD
    /subscriptions/XXXX-XXXX-XXXX-XXXX/resourceGroups/XXXX/providers/Microsoft.Network/networkInterfaces/aaXXXX["/subscriptions/XXXX-XXXX-XXXX-XXXX/resourceGroups/XXXX/providers/Microsoft.Network/networkInterfaces/aaXXXX"]
    ... (many more nodes and edges, all IDs obfuscated) ...
```

---

## Full Command Sequence

```bash
# 1. Build the Azure graph
azure-tenant-grapher build --tenant-id XXXX-XXXX-XXXX-XXXX --no-dashboard

# 2. Run the threat modeling agent
azure-tenant-grapher threat-model
```

---

## See Also

- [README](../README.md)
- [Product Requirements](../.github/azure-tenant-grapher-prd.md)
- [Project Specification](../.github/azure-tenant-grapher-spec.md)
