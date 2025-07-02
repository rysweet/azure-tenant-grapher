## spec

The `spec` command generates a tenant specification from the existing graph in Neo4j. This is useful for documentation, sharing, or further processing of your Azure environment. The command requires a running Neo4j database with a populated graph.

```bash
uv run azure-tenant-grapher spec
```

**Output:**
```text
✅ Configuration validation successful
INFO:src.config_manager:📝 Logging configured: level=INFO, file=console
INFO:src.llm_descriptions:{"endpoint": "https://ai-adapt-oai-eastus2.openai.azure.com/", "api_key_set": true, "api_version": "2025-01-01-preview", "model_chat": "o3", "model_reasoning": "o3", "event": "Loaded LLMConfig from environment", "timestamp": "...", "level": "info"}
INFO:src.llm_descriptions:{"endpoint": "https://ai-adapt-oai-eastus2.openai.azure.com/", "event": "Initialized Azure LLM Description Generator", "timestamp": "...", "level": "info"}
INFO:src.config_manager:============================================================
INFO:src.config_manager:🔧 AZURE TENANT GRAPHER CONFIGURATION
INFO:src.config_manager:============================================================
INFO:src.config_manager:📋 Tenant ID: [REDACTED]
INFO:src.config_manager:🗄️  Neo4j: bolt://localhost:7687 (user: neo4j)
INFO:src.config_manager:🤖 Azure OpenAI: https://ai-adapt-o....azure.com
INFO:src.config_manager:⚙️  Processing:
INFO:src.config_manager:   - Resource Limit: Unlimited
INFO:src.config_manager:   - Max Concurrency: 5
INFO:src.config_manager:   - Max Retries: 3
INFO:src.config_manager:   - Parallel Processing: True
INFO:src.config_manager:   - Auto Start Container: True
INFO:src.config_manager:📄 Specification:
INFO:src.config_manager:   - Spec Resource Limit: None
INFO:src.config_manager:   - Output Directory: .
INFO:src.config_manager:   - Include AI Summaries: True
INFO:src.config_manager:   - Include Config Details: True
INFO:src.config_manager:   - Template Style: comprehensive
INFO:src.config_manager:📝 Logging Level: INFO
INFO:src.config_manager:============================================================
📋 Generating tenant specification from existing graph...
ERROR:src.services.tenant_specification_service:Failed to generate tenant specification
Traceback (most recent call last):
  ...
src.exceptions.Neo4jConnectionError: [NEO4J_CONNECTION_FAILED] Failed to connect to Neo4j database (context: config_uri=bolt://localhost:7687, uri=bolt://localhost:7687) (caused by: Couldn't connect to localhost:7687 (resolved to ('[::1]:7687', '127.0.0.1:7687')):
Failed to establish connection to ResolvedIPv6Address(('::1', 7687, 0, 0)) (reason [Errno 61] Connection refused)
Failed to establish connection to ResolvedIPv4Address(('127.0.0.1', 7687)) (reason [Errno 61] Connection refused)) (suggestion: Check Neo4j connection settings and ensure the database is running)
ERROR:src.azure_tenant_grapher:Error generating tenant specification
Traceback (most recent call last):
  ...
src.exceptions.TenantSpecificationError: [TENANT_SPECIFICATION_FAILED] Failed to generate tenant specification. (context: output_path=...)
✅ Tenant specification generated successfully
```

**Troubleshooting:**
- If you see a connection error, ensure Neo4j is running and accessible at the configured URI. The graph must be built before running this command.
