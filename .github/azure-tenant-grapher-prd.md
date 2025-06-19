# Azure Tenant Grapher - Product Requirements Document

## Product Overview

**Azure Tenant Grapher** is a Python application that exhaustively discovers Azure tenant resources and builds a Neo4j graph database representation of those resources and their relationships. The application provides comprehensive resource mapping, interactive 3D visualization, Rich CLI dashboard interface, anonymized tenant specifications, Infrastructure-as-Code generation, and optional AI-powered documentation generation.

**New Feature: Agent Mode (MCP/AutoGen Integration)**  
Azure Tenant Grapher now includes an "agent mode" that enables users to ask natural language questions about their Azure graph/tenant data. This is powered by an AutoGen agent that chains tool calls (via the MCP server) to answer questions using the Neo4j graph database.

---

## Core Functional Requirements

### 12. Agent Mode (MCP/AutoGen Integration)

#### FR12.1 Agent Mode CLI

- **Requirement**: Provide a CLI command to launch an AutoGen-powered agent that can answer questions about the Azure graph/tenant.
- **Command**: `azure-tenant-grapher agent-mode [--question "your question here"]`
- **Modes**:
  - **Interactive**: User types questions in a REPL loop.
  - **Non-interactive**: User provides a question via `--question` and receives a direct answer.

#### FR12.2 Multi-Step Tool Chaining

- **Requirement**: The agent must be able to chain multiple tool calls to answer a question.
- **Workflow**:
  1. **Schema Discovery**: Agent first calls `get_neo4j_schema` to understand the graph structure.
  2. **Cypher Query**: Agent then calls `read_neo4j_cypher` to query the database for the answer.
  3. **Final Answer**: Agent provides a clear, human-readable answer based on the query results.

#### FR12.3 MCP Server Integration

- **Requirement**: Agent mode communicates with the MCP server (`mcp-neo4j-cypher`) for all tool calls.
- **Features**:
  - Automatic MCP server startup and management
  - Environment variable configuration for Neo4j connection
  - Diagnostic output for tool calls and query results

#### FR12.4 Robust Answer Generation

- **Requirement**: Agent must always provide a final, user-friendly answer (not just tool output).
- **Features**:
  - Handles empty results gracefully
  - Provides diagnostic output if no matching resources are found
  - Prints a sample of resource types if the answer is zero

#### FR12.5 End-to-End Testing

- **Requirement**: End-to-end tests validate that agent mode answers questions completely and correctly.
- **Tests**:
  - Agent mode must call both `get_neo4j_schema` and `read_neo4j_cypher`
  - Agent mode must provide a numeric answer for resource count questions
  - Tests fail if the agent stops after the first tool call or does not provide a final answer

---

## CLI Usage

```bash
# Start agent mode interactively
azure-tenant-grapher agent-mode

# Ask a question non-interactively
azure-tenant-grapher agent-mode --question "How many storage resources are in the tenant?"
```

- The agent will print a final answer, e.g.:
  ```
  🎯 Final Answer: There are 3 storage resources in the tenant.
  ```

- If no matching resources are found, the agent will print a diagnostic sample of resource types in the database.

---

## Implementation Status

- **Agent mode** is implemented in `src/agent_mode.py` and integrated into the CLI.
- **MCP server** is managed automatically and supports all required tool calls.
- **End-to-end tests** are provided in `tests/test_agent_mode_end_to_end.py` to ensure agent mode correctness.

---

## Change Notes

- feat: MCP server & AutoGen agent CLI (`mcp-server`, `agent-mode`) and docs ([#41](https://github.com/your-repo/azure-tenant-grapher/issues/41))
- feat: End-to-end agent mode testing and robust answer generation
