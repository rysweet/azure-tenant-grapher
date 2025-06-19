# Azure Tenant Grapher

Azure Tenant Grapher is a Python application that discovers all Azure resources in a tenant, builds a Neo4j graph database, and provides advanced visualization, documentation, and Infrastructure-as-Code (IaC) generation. It features a modular architecture, a Rich CLI dashboard, 3D graph visualization, anonymized tenant specifications, and optional AI-powered resource descriptions.

---

## Key Features

- **Exhaustive Azure resource discovery** across all subscriptions
- **Neo4j graph database** with rich schema and relationship modeling
- **Interactive 3D visualization** (HTML export, filtering, search)
- **Rich CLI dashboard** with live progress, logs, and configuration
- **AI-powered documentation** and tenant specification generation
- **Infrastructure-as-Code generation** (Terraform, ARM, Bicep)
- **Automated CLI tool management** and cross-platform support
- **Comprehensive test suite** (unit, integration, end-to-end)
- **Agent Mode (MCP/AutoGen Integration)**: Ask natural language questions about your Azure graph/tenant data

---

## Agent Mode (MCP/AutoGen Integration)

**Agent mode** enables you to ask natural language questions about your Azure graph/tenant data. The agent automatically chains tool calls (via the MCP server) to answer questions using the Neo4j graph database.

### How it works

- The agent receives a question (from CLI or REPL)
- Calls `get_neo4j_schema` to understand the graph
- Calls `read_neo4j_cypher` to answer the question
- Prints a final answer (e.g., "There are 3 storage resources in the tenant.")
- If no results, prints a diagnostic sample of resource types

### Usage

```bash
# Start agent mode interactively
azure-tenant-grapher agent-mode

# Ask a question non-interactively
azure-tenant-grapher agent-mode --question "How many storage resources are in the tenant?"
```

### Example Output

```
MCP Agent is ready
🤖 Processing question: How many storage resources are in the tenant?
🔄 Step 1: Getting database schema...
✅ Schema retrieved
🔄 Step 2: Querying for storage resources...
✅ Query executed
🔄 Step 3: Processing results...
🎯 Final Answer: There are 3 storage resources in the tenant.

🔎 Diagnostic: Sampling resource types in the database...
Sample resource types: [{"type": "Microsoft.Storage/storageAccounts", "count": 3}, ...]
```

### End-to-End Testing

- See `tests/test_agent_mode_end_to_end.py` for full end-to-end tests that ensure agent mode answers questions completely and correctly.

---

## CLI Reference

See `.github/azure-tenant-grapher-prd.md` and `.github/azure-tenant-grapher-spec.md` for full product requirements and project specification, including agent mode and MCP server details.

---

## Quick Start

```bash
# Install dependencies
uv pip install -r requirements.txt

# Start Neo4j (auto-managed by the app, or use docker-compose)
docker-compose up -d

# Build the graph
azure-tenant-grapher build --tenant-id <your-tenant-id>

# Start agent mode
azure-tenant-grapher agent-mode

# Ask a question non-interactively
azure-tenant-grapher agent-mode --question "How many storage resources are in the tenant?"
```

---

## Documentation

- [Product Requirements](.github/azure-tenant-grapher-prd.md)
- [Project Specification](.github/azure-tenant-grapher-spec.md)
- [3D Visualization](docs/design/iac_subset_bicep.md)
- [IaC Generation](docs/design/iac_subset_bicep.md)
- [Testing](tests/)

---

## License

MIT License. See [LICENSE](LICENSE) for details.
