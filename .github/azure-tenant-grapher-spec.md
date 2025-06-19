# Azure Tenant Grapher - Complete Project Specification

## Project Overview

**Azure Tenant Grapher** is a Python application that exhaustively walks Azure tenant resources and builds a Neo4j graph database representation of those resources and their relationships. The project features modular architecture, comprehensive testing, interactive Rich CLI dashboard, 3D visualization capabilities, Infrastructure-as-Code generation (Terraform, ARM, Bicep), anonymized tenant specifications, automated CLI tool management, and optional AI-powered resource descriptions. A complementary .NET implementation is also available for enterprise scenarios.

---

## Agent Mode (MCP/AutoGen Integration)

### Overview

Agent mode enables users to ask natural language questions about their Azure graph/tenant data. It is powered by an AutoGen agent that chains tool calls (via the MCP server) to answer questions using the Neo4j graph database.

### Key Features

- **Multi-step tool chaining**: The agent automatically calls `get_neo4j_schema` to understand the graph, then `read_neo4j_cypher` to answer the question, and finally provides a clear, human-readable answer.
- **CLI integration**: Launch agent mode with `azure-tenant-grapher agent-mode` (interactive) or `--question "your question"` (non-interactive).
- **MCP server orchestration**: Agent mode manages the MCP server lifecycle and uses it for all tool calls.
- **Robust answer generation**: The agent always provides a final answer, not just tool output. If no results are found, it prints a diagnostic sample of resource types.
- **End-to-end tested**: Tests in `tests/test_agent_mode_end_to_end.py` ensure agent mode answers questions completely and correctly.

### Implementation Details

- **Location**: `src/agent_mode.py`
- **CLI Command**: `azure-tenant-grapher agent-mode [--question "your question here"]`
- **Workflow**:
  1. Agent receives a question (from CLI or REPL)
  2. Calls `get_neo4j_schema` to understand the graph
  3. Calls `read_neo4j_cypher` to answer the question
  4. Prints a final answer (e.g., "There are 3 storage resources in the tenant.")
  5. If no results, prints a diagnostic sample of resource types

### Example Usage

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

- **Test file**: `tests/test_agent_mode_end_to_end.py`
- **Tests**:
  - Agent mode must call both `get_neo4j_schema` and `read_neo4j_cypher`
  - Agent mode must provide a numeric answer for resource count questions
  - Tests fail if the agent stops after the first tool call or does not provide a final answer

---

## CLI Reference

See the README for full CLI usage, including agent mode and MCP server commands.

---

## Implementation Status

- Agent mode is fully implemented and tested.
- MCP server is managed automatically and supports all required tool calls.
- End-to-end tests ensure agent mode correctness and robustness.
