# ATG Remote API - Design Summary

**Status:** Contract Defined (Implementation Pending)
**Version:** 1.0.0
**Date:** 2025-12-09

## What We Built

Complete REST API contract for Azure Tenant Grapher remote service, following the bricks & studs philosophy where the OpenAPI specification is the stable "stud" that implementations connect to.

## Key Files

| File | Purpose |
|------|---------|
| `openapi.yaml` | **THE CONTRACT** - Complete API specification (1,000+ lines) |
| `README.md` | Usage guide, examples, implementation notes |
| `API_DESIGN_DECISIONS.md` | 15 architectural decisions with rationale |
| `examples/*.json` | Request/response examples for all operations |
| `examples/sse_progress_stream.txt` | Server-Sent Events example |

## API Overview

### Core Pattern: Async Job Queue

All long-running operations follow this pattern:

```
1. Submit Job     → POST /v1/jobs/{operation}  → Returns job_id
2. Monitor        → GET /v1/jobs/{job_id}      → Poll status
   (or stream)    → GET /v1/jobs/{job_id}/progress (SSE)
3. Get Results    → GET /v1/jobs/{job_id}/results
4. Download Files → GET /v1/files/{file_id}
```

### Supported Operations

All 7 CLI commands mapped to REST endpoints:

- **scan** - Build Azure tenant graph (20+ min)
- **generate-spec** - Generate tenant specification
- **generate-iac** - Generate IaC (Terraform/ARM/Bicep)
- **create-tenant** - Create tenant from spec
- **visualize** - Generate graph visualization
- **threat-model** - Run threat modeling analysis
- **agent-mode** - Ask agent a question

### Authentication

Simple API key in header:
```http
X-API-Key: your-api-key-here
```

### Error Handling

Consistent error format across all endpoints:
```json
{
  "error": {
    "code": "INVALID_TENANT_ID",
    "message": "Human-readable error",
    "details": { "additional": "context" }
  }
}
```

## Design Highlights

### 1. Long-Running Operations Handled Properly

**Problem:** Scan operations can take 20+ minutes
**Solution:** Async job pattern + SSE for progress
**Benefit:** Clients can disconnect/reconnect without losing job

### 2. Real-Time Progress Without Polling Overhead

**Problem:** Polling every second creates 1,200+ requests
**Solution:** Server-Sent Events (SSE) stream for progress
**Benefit:** Real-time updates with minimal server load

### 3. Type-Safe Operation-Specific Schemas

**Problem:** Generic params lose type safety
**Solution:** Each operation has dedicated request schema
**Benefit:** Validate at API boundary, clear documentation

### 4. Cross-Tenant Support Built In

**Problem:** CLI supports cross-tenant IaC generation
**Solution:** `target_tenant_id` parameter in IaC requests
**Benefit:** Same API for same-tenant and cross-tenant

### 5. File Downloads Separate from Results

**Problem:** Large files (MB+) shouldn't be in JSON
**Solution:** Results contain metadata, files downloaded separately
**Benefit:** Efficient, resumable, proper Content-Type

## Example Workflows

### Scan Tenant with Progress Streaming

```bash
# 1. Submit job
curl -X POST https://api.atg.example.com/v1/jobs/scan \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "12345678-...", "generate_spec": true}'

# Response: {"job_id": "550e8400-...", "status": "pending"}

# 2. Stream progress (SSE)
curl -N -H "X-API-Key: $API_KEY" \
  https://api.atg.example.com/v1/jobs/550e8400-.../progress

# Output (live):
# event: progress
# data: {"progress": 10, "message": "Discovered 3 subscriptions"}
# ...
# event: complete
# data: {"status": "completed"}

# 3. Get results
curl -H "X-API-Key: $API_KEY" \
  https://api.atg.example.com/v1/jobs/550e8400-.../results

# 4. Download generated spec
curl -H "X-API-Key: $API_KEY" \
  https://api.atg.example.com/v1/files/abc123... -o tenant_spec.md
```

### Generate Cross-Tenant IaC

```bash
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

## Implementation Roadmap

### Phase 1: Server Foundation
- [ ] FastAPI server with OpenAPI auto-generation
- [ ] API key authentication (database-backed)
- [ ] Health check endpoint
- [ ] Basic error handling

### Phase 2: Job Queue
- [ ] Celery + Redis for async job processing
- [ ] Job status tracking (pending/running/completed/failed)
- [ ] Job result storage
- [ ] Job cancellation

### Phase 3: Progress Streaming
- [ ] SSE endpoint for progress updates
- [ ] Progress event publishing from workers
- [ ] Connection management (reconnect, timeout)

### Phase 4: CLI Integration
- [ ] Execute CLI commands from workers
- [ ] Capture output and progress
- [ ] Map CLI results to API responses

### Phase 5: File Management
- [ ] File storage (Azure Blob or S3)
- [ ] File download endpoint with range support
- [ ] File cleanup/expiration

### Phase 6: Operations Coverage
- [ ] Implement all 7 operations
- [ ] Operation-specific result handling
- [ ] Test each operation end-to-end

### Phase 7: Production Readiness
- [ ] Rate limiting per API key
- [ ] Metrics and monitoring (Prometheus)
- [ ] Structured logging
- [ ] Documentation generation from OpenAPI
- [ ] Load testing

## Technical Decisions

Key architectural decisions (see API_DESIGN_DECISIONS.md for details):

1. **Async job pattern** - Handles 20+ minute operations gracefully
2. **SSE for progress** - Real-time updates without polling overhead
3. **API key in header** - Secure, standard, works with CORS
4. **Separate endpoints per operation** - Clear, type-safe, easy to extend
5. **Results stored server-side** - Enables resumable downloads
6. **File downloads separate** - Efficient, proper Content-Type
7. **Standard error format** - Consistent, machine-readable
8. **FastAPI recommended** - Async, type-safe, auto-generates docs
9. **Celery + Redis recommended** - Proven job queue solution

## Philosophy Alignment

This API follows ATG's core principles:

✅ **Ruthless Simplicity**
- Single pattern (async jobs) for all operations
- No unnecessary abstractions
- Clear, predictable behavior

✅ **Bricks & Studs**
- OpenAPI spec is the "stud" (stable contract)
- Server implementation is the "brick" (regeneratable)
- Clear separation between contract and implementation

✅ **Zero-BS Implementation**
- No placeholder endpoints
- Every endpoint has clear purpose
- All operations map directly to CLI commands

✅ **Regeneratable**
- Server can be rebuilt from OpenAPI spec
- Contract stays stable across implementations
- Clients unaffected by server rewrites

## What's Next

1. **Validate Contract**: Run OpenAPI validation (`swagger-cli validate openapi.yaml`)
2. **Mock Server**: Test with Prism mock server
3. **Client Testing**: Build test client to verify contract usability
4. **Server Implementation**: Start Phase 1 (FastAPI foundation)

## Metrics

- **OpenAPI Spec**: 1,000+ lines
- **Endpoints Defined**: 15
- **Operations Supported**: 7
- **Request Schemas**: 7
- **Response Schemas**: 9
- **Error Codes**: 7
- **Design Decisions Documented**: 15
- **Example Files**: 7

## References

- OpenAPI Spec: `openapi.yaml`
- Usage Guide: `README.md`
- Design Decisions: `API_DESIGN_DECISIONS.md`
- Request/Response Examples: `examples/`
- Bricks & Studs Philosophy: `@.claude/context/PHILOSOPHY.md`

---

**Contract Status:** ✅ Complete and ready for implementation
**Next Step:** Validate OpenAPI spec with `swagger-cli validate openapi.yaml`
