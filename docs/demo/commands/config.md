## config

The `config` command displays the current configuration template for Azure Tenant Grapher, including tenant ID, Neo4j connection, Azure OpenAI settings, processing options, logging, and specification generation. Use this command to verify your environment and see which settings are active.

```bash
uv run azure-tenant-grapher config
```

**Output:**
```text
✅ Configuration validation successful
🔧 Current Configuration Template:
============================================================
tenant_id: example-tenant-id
neo4j:
  uri: bolt://localhost:7687
  user: neo4j
azure_openai:
  endpoint: https://ai-adapt-o....azure.com
  api_version: 2025-01-01-preview
  model_chat: o3
  model_reasoning: o3
  configured: True
processing:
  resource_limit: None
  max_concurrency: 5
  max_retries: 3
  retry_delay: 1.0
  parallel_processing: True
  auto_start_container: True
logging:
  level: INFO
  file_output: None
specification:
  resource_limit: None
  output_directory: .
  include_ai_summaries: True
  include_configuration_details: True
  anonymization_seed: None
  template_style: comprehensive
============================================================
💡 Set environment variables to customize configuration
```

**Troubleshooting:**
- If you see an error, check that your `.env` file is present and correctly filled out. The command will show which fields are missing or misconfigured.
