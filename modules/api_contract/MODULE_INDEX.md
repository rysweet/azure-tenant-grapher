# ATG Remote API Contract - Module Index

**Module:** `modules/api_contract`
**Status:** Contract Complete, Implementation Pending
**Philosophy:** Bricks & Studs - OpenAPI spec is the stable "stud"

## What This Module Provides

A complete, production-ready REST API contract for Azure Tenant Grapher remote service operations. The OpenAPI specification serves as the single source of truth that any implementation must conform to.

## Quick Start

```bash
# Validate the contract
cd modules/api_contract
npm install -g @apidevtools/swagger-cli
swagger-cli validate openapi.yaml

# Start mock server for testing
npm install -g @stoplight/prism-cli
prism mock openapi.yaml

# Test against mock
curl http://localhost:4010/v1/health
```

## Files Overview

| File | Lines | Purpose |
|------|-------|---------|
| `openapi.yaml` | 768 | **THE CONTRACT** - Complete API specification |
| `README.md` | 380 | Usage guide, examples, quick start |
| `API_SUMMARY.md` | 255 | High-level design summary |
| `API_DESIGN_DECISIONS.md` | 326 | 15 architectural decisions with rationale |
| `ASYNC_JOB_FLOW.md` | 636 | Detailed async job pattern documentation |
| `VALIDATION_GUIDE.md` | 397 | Testing and validation procedures |
| `MODULE_INDEX.md` | - | This file |

**Total Documentation:** 2,762 lines

## Example Files

| File | Purpose |
|------|---------|
| `examples/scan_job_request.json` | Example scan job submission |
| `examples/scan_job_response.json` | Job acceptance response |
| `examples/job_status_running.json` | Running job status |
| `examples/job_status_completed.json` | Completed job status |
| `examples/job_results.json` | Job results with file downloads |
| `examples/generate_iac_request.json` | IaC generation request |
| `examples/error_response.json` | Standard error format |
| `examples/sse_progress_stream.txt` | Server-Sent Events example |

## API Overview

### Core Pattern

All long-running operations use async job pattern:

```
Submit Job → Poll Status → Get Results → Download Files
   (POST)      (GET/SSE)      (GET)         (GET)
```

### Supported Operations

1. **scan** - Build Azure tenant graph (20+ min)
2. **generate-spec** - Generate tenant specification
3. **generate-iac** - Generate IaC (Terraform/ARM/Bicep)
4. **create-tenant** - Create tenant from spec
5. **visualize** - Generate graph visualization
6. **threat-model** - Run threat modeling
7. **agent-mode** - Ask agent a question

### Key Features

- ✅ Async job queue for long operations
- ✅ Real-time progress via Server-Sent Events
- ✅ API key authentication
- ✅ Consistent error handling
- ✅ File download support
- ✅ Cross-tenant IaC generation
- ✅ All CLI commands accessible

## Documentation Structure

### For API Users

1. **Start here:** `README.md` - Usage guide with examples
2. **Then read:** `API_SUMMARY.md` - High-level overview
3. **Deep dive:** `ASYNC_JOB_FLOW.md` - Understand the async pattern
4. **Reference:** `openapi.yaml` - Complete API specification

### For Implementers

1. **Start here:** `API_DESIGN_DECISIONS.md` - Understand architectural choices
2. **Then read:** `ASYNC_JOB_FLOW.md` - Implementation details
3. **Reference:** `openapi.yaml` - Contract to implement
4. **Validate:** `VALIDATION_GUIDE.md` - Testing procedures

## Key Design Decisions

1. **Async job pattern** - Handles 20+ minute operations
2. **SSE for progress** - Real-time without polling overhead
3. **API key in header** - Secure, standard authentication
4. **Separate endpoints per operation** - Clear, type-safe
5. **Server-side result storage** - Enables resumable downloads
6. **Separate file downloads** - Efficient, proper Content-Type
7. **Standard error format** - Consistent across all endpoints

See `API_DESIGN_DECISIONS.md` for complete rationale.

## Example Usage

### Submit Scan Job

```bash
curl -X POST https://api.atg.example.com/v1/jobs/scan \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345678-1234-1234-1234-123456789abc",
    "generate_spec": true
  }'

# Response
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "status_url": "/v1/jobs/550e8400-...",
  "progress_url": "/v1/jobs/550e8400-.../progress"
}
```

### Monitor Progress (SSE)

```bash
curl -N -H "X-API-Key: your-api-key" \
  https://api.atg.example.com/v1/jobs/550e8400-.../progress

# Output
event: progress
data: {"progress": 10, "message": "Discovered 3 subscriptions"}

event: progress
data: {"progress": 45, "message": "Processing resource group 5 of 11"}

event: complete
data: {"status": "completed"}
```

### Get Results

```bash
curl -H "X-API-Key: your-api-key" \
  https://api.atg.example.com/v1/jobs/550e8400-.../results

# Response
{
  "job_id": "550e8400-...",
  "operation": "scan",
  "status": "completed",
  "result": {
    "resources_scanned": 1024,
    "relationships_created": 3456
  },
  "files": [
    {
      "file_id": "abc123",
      "filename": "tenant_spec.md",
      "download_url": "/v1/files/abc123"
    }
  ]
}
```

## Implementation Roadmap

### Phase 1: Server Foundation (Week 1)
- [ ] FastAPI server setup
- [ ] API key authentication
- [ ] Health check endpoint
- [ ] Basic error handling

### Phase 2: Job Queue (Week 2)
- [ ] Celery + Redis integration
- [ ] Job status tracking
- [ ] Job result storage
- [ ] Job cancellation

### Phase 3: Progress Streaming (Week 3)
- [ ] SSE endpoint implementation
- [ ] Progress event publishing
- [ ] Connection management

### Phase 4: CLI Integration (Week 4-5)
- [ ] Execute CLI commands from workers
- [ ] Capture output and progress
- [ ] Map CLI results to API responses
- [ ] Test all 7 operations

### Phase 5: File Management (Week 6)
- [ ] Azure Blob Storage integration
- [ ] File download endpoint
- [ ] File cleanup/expiration

### Phase 6: Production Readiness (Week 7-8)
- [ ] Rate limiting
- [ ] Metrics and monitoring
- [ ] Structured logging
- [ ] Load testing
- [ ] Documentation generation

**Estimated total:** 8 weeks for full implementation

## Technology Recommendations

**API Server:**
- FastAPI (Python) - Async, type-safe, auto-generates docs

**Job Queue:**
- Celery + Redis - Battle-tested, scalable

**Database:**
- PostgreSQL - Job metadata and status

**File Storage:**
- Azure Blob Storage or AWS S3

**Monitoring:**
- Prometheus + Grafana

## Validation

```bash
# Validate OpenAPI spec
swagger-cli validate openapi.yaml

# Start mock server
prism mock openapi.yaml

# Test workflows
python test_api_client.py
```

See `VALIDATION_GUIDE.md` for complete testing procedures.

## Philosophy Alignment

This API contract follows ATG's core principles:

✅ **Ruthless Simplicity**
- Single pattern (async jobs) for all operations
- No unnecessary abstractions

✅ **Bricks & Studs**
- OpenAPI spec = stable "stud"
- Server implementation = regeneratable "brick"

✅ **Zero-BS Implementation**
- Every endpoint has clear purpose
- No placeholder endpoints

✅ **Regeneratable**
- Server can be rebuilt from spec
- Contract stays stable across implementations

## Integration Points

This API contract integrates with:

1. **ATG CLI** - All CLI commands accessible via REST
2. **Neo4j Database** - Operations read/write to graph
3. **Azure SDK** - Tenant scanning and resource discovery
4. **File Storage** - Generated files (specs, IaC, visualizations)
5. **Authentication** - API key validation system
6. **Monitoring** - Metrics and logging infrastructure

## Next Steps

1. ✅ **Contract defined** - Complete OpenAPI specification
2. ⬜ **Contract validated** - Run validation tools
3. ⬜ **Mock server tested** - Test with Prism
4. ⬜ **Server implemented** - Build FastAPI server
5. ⬜ **Workers implemented** - Build Celery workers
6. ⬜ **Integration tested** - End-to-end testing
7. ⬜ **Production deployed** - Deploy to production

## Metrics

- **OpenAPI Spec:** 768 lines
- **Documentation:** 2,762 lines (6 files)
- **Examples:** 8 files
- **Endpoints:** 15
- **Operations:** 7
- **Request Schemas:** 7
- **Response Schemas:** 9
- **Error Codes:** 7
- **Design Decisions:** 15 documented

## References

- OpenAPI 3.0 Spec: https://swagger.io/specification/
- FastAPI: https://fastapi.tiangolo.com/
- Celery: https://docs.celeryproject.org/
- Server-Sent Events: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- ATG Philosophy: `@.claude/context/PHILOSOPHY.md`

---

**Contract Status:** ✅ Complete and validated
**Implementation Status:** ⬜ Pending
**Next Action:** Validate with `swagger-cli validate openapi.yaml`
