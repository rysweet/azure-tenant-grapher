# Threat Modeling Agent Demo

This demo illustrates the end-to-end workflow of the Threat Modeling Agent using the provided demo tenant.

## Demo Tenant Configuration

The following environment variables are used (from `.env`):

```
AZURE_TENANT_ID=3cd87a41-1f61-4aef-a212-cefdecd9a2d1
NEO4J_URI=bolt://localhost:8768
NEO4J_USER=neo4j
NEO4J_PASSWORD=azure-grapher-2024
AZURE_OPENAI_ENDPOINT=https://ai-adapt-oai-eastus2.openai.azure.com/
AZURE_OPENAI_KEY=***
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_MODEL_CHAT=o3
AZURE_OPENAI_MODEL_REASONING=o3
```

## Step 1: Build the Azure Graph

```bash
azure-tenant-grapher build --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1
```

**Sample Output:**
```
[INFO] Discovering Azure resources for tenant 3cd87a41-1f61-4aef-a212-cefdecd9a2d1...
[INFO] Found 42 subscriptions, 300 resources.
[INFO] Writing graph to Neo4j at bolt://localhost:8768...
[INFO] Graph build complete.
```

## Step 2: Generate Threat Model

```bash
azure-tenant-grapher threat-model --spec-path ./demo-tenant-spec.json --summaries-path ./demo-llm-summaries.json
```

**Sample Output:**
```
[INFO] Building DFD (Data Flow Diagram)...
[INFO] DFD artifact (Mermaid diagram) generated: docs/artifacts/demo_dfd.mmd
[INFO] Running Microsoft Threat Modeling Tool (TMT)...
[INFO] TMT runner output: 12 threats identified.
[INFO] Mapping threats to ASB controls...
[INFO] Markdown report generated: docs/artifacts/demo_threat_model_report.md
```

- [Mermaid DFD Diagram](artifacts/demo_dfd.mmd)
- [Threat Model Markdown Report](artifacts/demo_threat_model_report.md)

## Step 3: View the Mermaid DFD

Open the generated Mermaid file in a Mermaid live editor or compatible tool:

```
flowchart TD
    user1((User))
    app1["App Service"]
    db1[(("SQL DB"))]
    user1 -->|HTTPS| app1
    app1 -->|TCP 1433| db1
```

## Step 4: Review the Threat Model Report

The generated Markdown report includes:

- DFD diagram (embedded)
- Table of identified threats
- Mapped ASB controls for each threat

**Extract:**
```
| Threat ID | Title           | Severity | STRIDE | ASB Controls         |
|-----------|----------------|----------|--------|----------------------|
| TMT-001   | Data Exposure  | High     | I      | ASB-DS-4, ASB-DS-5   |
| TMT-002   | Privilege Esc. | Medium   | E      | ASB-IM-2, ASB-IM-3   |
...
```

## Step 5: Links to Artifacts

- [DFD Mermaid Diagram (demo_dfd.mmd)](artifacts/demo_dfd.mmd)
- [Threat Model Report (demo_threat_model_report.md)](artifacts/demo_threat_model_report.md)

---

## Full Command Sequence

```bash
# 1. Build the Azure graph
azure-tenant-grapher build --tenant-id 3cd87a41-1f61-4aef-a212-cefdecd9a2d1

# 2. Generate the threat model
azure-tenant-grapher threat-model --spec-path ./demo-tenant-spec.json --summaries-path ./demo-llm-summaries.json

# 3. View the DFD and report in docs/artifacts/
```

---

## See Also

- [README](../README.md)
- [Product Requirements](../.github/azure-tenant-grapher-prd.md)
- [Project Specification](../.github/azure-tenant-grapher-spec.md)
