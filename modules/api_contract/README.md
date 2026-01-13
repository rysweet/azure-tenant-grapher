# ATG Remote API Contract

**Philosophy:** Bricks & Studs - Clean, stable REST API contract for remote ATG operations.

## Overview

This module defines the REST API contract for Azure Tenant Grapher remote service. The API is designed around an async job pattern to handle long-running operations (20+ minute scans) efficiently.

## Architecture

### Design Principles

1. **Async Job Pattern**: Long operations return immediately with job ID, clients poll for status
2. **Progress Streaming**: Real-time updates via Server-Sent Events (SSE)
3. **Simple Authentication**: API key in header (`X-API-Key`)
4. **RESTful Pragmatism**: Follow REST when it adds clarity, use RPC-style for complex operations
5. **Error Consistency**: Standardized error format across all endpoints

### API Contract (The "Stud")

The OpenAPI specification (`openapi.yaml`) is the single source of truth. All implementations must conform to this contract.

**Public Interface:**
- `openapi.yaml` - Complete API specification
- All endpoints documented with request/response schemas
- Error codes and formats defined

## Quick Start

### Submit a Job

```bash
# Scan tenant
curl -X POST https://api.atg.example.com/v1/jobs/scan \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345678-1234-1234-1234-123456789abc",
    "max_llm_threads": 5,
    "generate_spec": true
  }'

# Response
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "status_url": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000",
  "progress_url": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000/progress"
}
```

### Poll Job Status

```bash
curl -X GET https://api.atg.example.com/v1/jobs/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: your-api-key"

# Response
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "operation": "scan",
  "status": "running",
  "progress": 45.5,
  "message": "Processing resource group 5 of 11",
  "created_at": "2025-12-09T10:00:00Z",
  "started_at": "2025-12-09T10:00:01Z"
}
```

### Stream Progress (SSE)

```bash
curl -N -H "X-API-Key: your-api-key" \
  https://api.atg.example.com/v1/jobs/550e8400-e29b-41d4-a716-446655440000/progress

# Output
event: progress
data: {"job_id": "550e8400-...", "status": "running", "progress": 10, "message": "Discovering resources"}

event: progress
data: {"job_id": "550e8400-...", "status": "running", "progress": 45, "message": "Processing resource group 5 of 11"}

event: complete
data: {"job_id": "550e8400-...", "status": "completed"}
```

### Get Job Results

```bash
curl -X GET https://api.atg.example.com/v1/jobs/550e8400-e29b-41d4-a716-446655440000/results \
  -H "X-API-Key: your-api-key"

# Response
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "operation": "scan",
  "status": "completed",
  "result": {
    "resources_scanned": 1024,
    "relationships_created": 3456,
    "duration_seconds": 1234
  },
  "files": [
    {
      "file_id": "abc123",
      "filename": "tenant_spec.md",
      "mime_type": "text/markdown",
      "size": 45678,
      "download_url": "/v1/files/abc123"
    }
  ]
}
```

## Supported Operations

All CLI commands are accessible via REST API:

| Operation | Endpoint | Description |
|-----------|----------|-------------|
| `scan` | `POST /v1/jobs/scan` | Build Azure tenant graph |
| `generate-spec` | `POST /v1/jobs/generate-spec` | Generate tenant specification |
| `generate-iac` | `POST /v1/jobs/generate-iac` | Generate IaC (Terraform/ARM/Bicep) |
| `create-tenant` | `POST /v1/jobs/create-tenant` | Create tenant from spec |
| `visualize` | `POST /v1/jobs/visualize` | Generate graph visualization |
| `threat-model` | `POST /v1/jobs/threat-model` | Run threat modeling |
| `agent-mode` | `POST /v1/jobs/agent-mode` | Ask agent a question |

## Job Lifecycle

```
1. Submit Job
   POST /jobs/{operation}
   → Returns job_id, status: "pending"

2. Job Processing
   Status: pending → running → completed/failed/cancelled

3. Monitor Progress (choose one)
   a. Poll Status: GET /jobs/{job_id}
   b. Stream Progress: GET /jobs/{job_id}/progress (SSE)

4. Get Results
   GET /jobs/{job_id}/results
   → Returns result data + file download URLs

5. Download Files
   GET /files/{file_id}
   → Returns generated file
```

## Authentication

All endpoints (except `/health`) require API key authentication:

```http
X-API-Key: your-api-key-here
```

**Validate API Key:**
```bash
curl -X GET https://api.atg.example.com/v1/auth/validate \
  -H "X-API-Key: your-api-key"
```

## Error Handling

All errors follow consistent format:

```json
{
  "error": {
    "code": "INVALID_TENANT_ID",
    "message": "Tenant ID must be a valid GUID",
    "details": {
      "provided": "invalid-id",
      "expected_format": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    }
  }
}
```

**Common Error Codes:**
- `INVALID_API_KEY` (401) - API key missing or invalid
- `JOB_NOT_FOUND` (404) - Job ID does not exist
- `JOB_NOT_COMPLETED` (409) - Results requested before job finished
- `INVALID_TENANT_ID` (400) - Invalid tenant ID format
- `INVALID_REQUEST` (400) - Malformed request body
- `INTERNAL_ERROR` (500) - Server error

## Example Workflows

### Full Scan with Visualization

```bash
# 1. Submit scan job
JOB_ID=$(curl -X POST https://api.atg.example.com/v1/jobs/scan \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "12345678-...", "visualize": true}' | jq -r .job_id)

# 2. Stream progress
curl -N -H "X-API-Key: $API_KEY" \
  "https://api.atg.example.com/v1/jobs/$JOB_ID/progress" &

# 3. Wait for completion (poll every 30s)
while true; do
  STATUS=$(curl -s -H "X-API-Key: $API_KEY" \
    "https://api.atg.example.com/v1/jobs/$JOB_ID" | jq -r .status)

  if [[ "$STATUS" == "completed" ]]; then
    break
  elif [[ "$STATUS" == "failed" ]]; then
    echo "Job failed"
    exit 1
  fi

  sleep 30
done

# 4. Get results
curl -H "X-API-Key: $API_KEY" \
  "https://api.atg.example.com/v1/jobs/$JOB_ID/results" | jq .

# 5. Download visualization
FILE_ID=$(curl -s -H "X-API-Key: $API_KEY" \
  "https://api.atg.example.com/v1/jobs/$JOB_ID/results" | jq -r '.files[0].file_id')

curl -H "X-API-Key: $API_KEY" \
  "https://api.atg.example.com/v1/files/$FILE_ID" -o visualization.html
```

### Cross-Tenant IaC Generation

```bash
# Submit IaC generation with cross-tenant target
curl -X POST https://api.atg.example.com/v1/jobs/generate-iac \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "source-tenant-id",
    "target_tenant_id": "target-tenant-id",
    "format": "terraform",
    "auto_import_existing": true,
    "auto_register_providers": true
  }'
```

## Implementation Notes

### Server-Sent Events (SSE) for Progress

The progress endpoint uses SSE for real-time updates:

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

event: progress
data: {"job_id": "...", "progress": 45, "message": "..."}

event: complete
data: {"job_id": "...", "status": "completed"}
```

**Client handling:**
```javascript
const eventSource = new EventSource('/v1/jobs/JOB_ID/progress', {
  headers: { 'X-API-Key': apiKey }
});

eventSource.addEventListener('progress', (e) => {
  const data = JSON.parse(e.data);
  console.log(`Progress: ${data.progress}% - ${data.message}`);
});

eventSource.addEventListener('complete', (e) => {
  console.log('Job completed');
  eventSource.close();
});

eventSource.addEventListener('error', (e) => {
  const data = JSON.parse(e.data);
  console.error(`Job failed: ${data.error}`);
  eventSource.close();
});
```

### Job Queue Implementation

Jobs are processed by async worker pool:

1. Job submitted → Added to queue (Redis/in-memory)
2. Worker picks up job → Status: running
3. Worker executes CLI command
4. Progress updates published to SSE stream
5. Results stored with job ID
6. Files stored in object storage (S3/Azure Blob)

### Timeouts

- **Job submission**: 5 seconds max
- **Status polling**: 30 seconds max
- **SSE connection**: No timeout (keep-alive)
- **File download**: 5 minutes max
- **Job execution**: Operation-dependent (scan: 30+ min)

### Rate Limiting

Consider implementing per-API-key rate limits:
- Job submissions: 10/minute
- Status checks: 60/minute
- File downloads: 30/minute

## Testing the API

### OpenAPI Validation

```bash
# Install OpenAPI CLI tools
npm install -g @apidevtools/swagger-cli

# Validate OpenAPI spec
swagger-cli validate openapi.yaml
```

### Mock Server

```bash
# Install Prism mock server
npm install -g @stoplight/prism-cli

# Start mock server
prism mock openapi.yaml

# Test against mock
curl http://localhost:4010/v1/health
```

## Next Steps

1. **Implement Server**: Use FastAPI (Python) for server implementation
2. **Job Queue**: Use Celery + Redis for async job processing
3. **Authentication**: Implement API key validation with database
4. **File Storage**: Use Azure Blob Storage or S3 for generated files
5. **Monitoring**: Add metrics (Prometheus) and logging (structured JSON)

## Module Structure

```
modules/api_contract/
├── README.md           # This file
├── openapi.yaml       # Complete API specification (THE CONTRACT)
├── examples/          # Example requests/responses
│   ├── scan_job.json
│   ├── iac_job.json
│   └── sse_stream.txt
├── tests/             # Contract validation tests
│   └── test_openapi_validation.py
└── docs/              # Additional documentation
    ├── authentication.md
    ├── job_lifecycle.md
    └── error_handling.md
```

## Philosophy Alignment

This API contract follows ATG's core principles:

- **Ruthless Simplicity**: Single clear pattern (async jobs) for all operations
- **Bricks & Studs**: OpenAPI spec is the stable "stud", implementations are "bricks"
- **Regeneratable**: Server can be rebuilt from spec without breaking clients
- **Zero-BS**: Every endpoint has clear purpose, no placeholder endpoints

## References

- OpenAPI 3.0 Specification: https://swagger.io/specification/
- Server-Sent Events: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- REST API Design: https://restfulapi.net/
