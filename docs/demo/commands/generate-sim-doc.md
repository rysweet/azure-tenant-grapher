## generate-sim-doc

The `generate-sim-doc` command uses the Azure OpenAI LLM to generate a simulated customer profile for your Azure tenant. The `--size` flag controls the number of simulated users/resources. The output is written to a Markdown file in the `simdocs/` directory.

```bash
uv run azure-tenant-grapher generate-sim-doc --size 1
```

**Output:**
```text
{"endpoint": "https://ai-adapt-oai-eastus2.openai.azure.com/", "api_key_set": true, "api_version": "2025-01-01-preview", "model_chat": "o3", "model_reasoning": "o3", "event": "Loaded LLMConfig from environment", "timestamp": "...", "level": "info"}
{"endpoint": "https://ai-adapt-oai-eastus2.openai.azure.com/", "event": "Initialized Azure LLM Description Generator", "timestamp": "...", "level": "info"}
HTTP Request: POST https://ai-adapt-oai-eastus2.openai.azure.com/openai/deployments/o3/chat/completions?api-version=2025-01-01-preview "HTTP/1.1 200 OK"
{"event": "Generated simulated customer profile via LLM.", "timestamp": "...", "level": "info"}
✅ Simulated customer profile written to: simdocs/simdoc-YYYYMMDD-HHMMSS.md
```

**Troubleshooting:**
- If you see an error, check that your Azure OpenAI environment variables are set and valid. The command requires network access to the Azure OpenAI endpoint.
