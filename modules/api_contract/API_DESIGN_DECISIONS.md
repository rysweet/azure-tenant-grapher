# API Design Decisions

This document records key design decisions made for the ATG Remote API.

## Decision 1: Async Job Pattern for All Operations

**What was decided:** All long-running operations use an async job pattern (submit → poll → results)

**Why:**
- Scan operations can take 20+ minutes
- HTTP connections shouldn't stay open that long
- Clients need ability to disconnect/reconnect without losing job
- Enables multiple concurrent operations per client
- Standard pattern for long-running REST operations

**Alternatives considered:**
- **Synchronous endpoints with long timeout**: Would timeout, no recovery
- **WebSocket bidirectional**: More complex, harder to implement with standard tools
- **Callback URLs**: Requires client to expose endpoint, complex firewall rules

**Trade-offs:**
- Pro: Resilient, scalable, standard pattern
- Con: Clients must implement polling logic (but we provide SSE alternative)

---

## Decision 2: Server-Sent Events (SSE) for Progress

**What was decided:** Use SSE for real-time progress streaming, alongside polling

**Why:**
- Real-time updates without polling overhead
- Simpler than WebSocket (unidirectional, no handshake)
- Built into browsers, easy to use
- Falls back gracefully (clients can still poll)

**Alternatives considered:**
- **Polling only**: Works but creates high request volume for long jobs
- **WebSocket**: Overkill for one-way progress updates
- **Long polling**: Complicated, not standard

**Trade-offs:**
- Pro: Real-time, efficient, standard
- Con: Requires server SSE support, connection management

---

## Decision 3: API Key in Header (Not Query String)

**What was decided:** Use `X-API-Key` header for authentication

**Why:**
- Headers don't appear in logs by default
- Standard practice for API authentication
- Easier to rotate keys (no URL changes)
- Works with CORS

**Alternatives considered:**
- **Query string (?api_key=...)**: Appears in logs, not secure
- **Bearer token**: More complex (requires OAuth infrastructure)
- **mTLS**: Too complex for initial implementation

**Trade-offs:**
- Pro: Secure, standard, simple
- Con: Clients must remember to add header

---

## Decision 4: Separate Endpoints per Operation (Not Generic /jobs)

**What was decided:** Each operation gets dedicated endpoint (e.g., `/jobs/scan`, `/jobs/generate-iac`)

**Why:**
- Clear, self-documenting API
- Type-safe request schemas per operation
- Easy to add operation-specific options
- RESTful resource modeling

**Alternatives considered:**
- **Single /jobs endpoint with "operation" field**: Less clear, harder to document
- **Different base paths per operation (/scan/jobs, /iac/jobs)**: Inconsistent structure

**Trade-offs:**
- Pro: Clear, type-safe, easy to extend
- Con: More endpoints to maintain (but auto-generated from OpenAPI)

---

## Decision 5: Job Results Stored Server-Side (Not Inline)

**What was decided:** Results stored on server, accessed via `/jobs/{id}/results`

**Why:**
- Results can be large (MB+ for IaC files)
- Enables resumable downloads
- Clients can fetch results multiple times
- Allows results to persist after job completion

**Alternatives considered:**
- **Inline in status response**: Too large, repeated transfer
- **Only downloadable once**: Not user-friendly

**Trade-offs:**
- Pro: Efficient, flexible, resumable
- Con: Server must store results (requires storage layer)

---

## Decision 6: File Download via Separate Endpoint

**What was decided:** Generated files accessed via `/files/{file_id}`, not inline in results

**Why:**
- Enables proper Content-Type headers for each file
- Supports range requests (resumable downloads)
- Clean separation: results = metadata, files = data
- Easier to implement caching/CDN

**Alternatives considered:**
- **Inline base64 in JSON**: Bloated, inefficient
- **Direct URLs in results**: Exposes storage backend

**Trade-offs:**
- Pro: Clean, efficient, standard HTTP file serving
- Con: Two-step process (get results, then download files)

---

## Decision 7: Standard Error Format Across All Endpoints

**What was decided:** All errors use consistent `{error: {code, message, details}}` format

**Why:**
- Predictable error handling for clients
- Machine-readable error codes
- Human-readable messages
- Optional structured details for debugging

**Alternatives considered:**
- **Plain string errors**: Not structured, hard to parse
- **HTTP status only**: Not enough context
- **Different formats per endpoint**: Inconsistent, confusing

**Trade-offs:**
- Pro: Consistent, easy to handle, debuggable
- Con: None significant

---

## Decision 8: Operation-Specific Request Schemas (Not Generic Params)

**What was decided:** Each operation defines specific request schema matching CLI options

**Why:**
- Type safety (validate at API boundary)
- Clear documentation per operation
- Maps directly to CLI options (no translation)
- Easier for clients to construct valid requests

**Alternatives considered:**
- **Generic params object**: Loses type safety
- **CLI command string**: String injection risk, parsing complexity

**Trade-offs:**
- Pro: Type-safe, clear, maps to CLI
- Con: More schema definitions (but auto-validated)

---

## Decision 9: Polling Recommended Interval: 30 Seconds

**What was decided:** Documentation recommends 30-second polling interval

**Why:**
- Long operations (20+ min) don't need frequent checks
- Reduces server load
- Status changes are meaningful at this granularity
- SSE available for clients needing real-time updates

**Alternatives considered:**
- **5 seconds**: Too frequent for long operations
- **5 minutes**: Too slow for user feedback

**Trade-offs:**
- Pro: Balanced load vs responsiveness
- Con: 30s perceived lag (but SSE solves this)

---

## Decision 10: No Job Expiration in Initial Design

**What was decided:** Jobs and results persist indefinitely (v1.0)

**Why:**
- Simplifies initial implementation
- Users may need historical results
- Can add TTL/expiration later without breaking clients

**Alternatives considered:**
- **24-hour expiration**: May be too short for some workflows
- **User-configurable TTL**: More complex

**Trade-offs:**
- Pro: Simple, user-friendly
- Con: Storage grows unbounded (addressed in future versions)

---

## Decision 11: FastAPI for Server Implementation (Recommended)

**What was decided:** Recommend FastAPI (Python) for implementing server

**Why:**
- Native async/await support for long-running jobs
- Auto-generates OpenAPI docs from code
- Type hints validate requests automatically
- Python matches ATG CLI language
- Built-in SSE support via StreamingResponse

**Alternatives considered:**
- **Express (Node.js)**: Not Python, less type safety
- **Flask**: No native async, less modern
- **Django REST**: Heavier framework than needed

**Trade-offs:**
- Pro: Fast, modern, type-safe, matches CLI
- Con: Requires Python 3.8+ (not a real limitation)

---

## Decision 12: Celery + Redis for Job Queue (Recommended)

**What was decided:** Recommend Celery with Redis backend for job processing

**Why:**
- Battle-tested for async job processing
- Redis provides fast job queue and result storage
- Celery integrates with FastAPI easily
- Supports distributed workers (future scaling)

**Alternatives considered:**
- **RQ (Redis Queue)**: Simpler but less feature-complete
- **In-memory queue**: Not persistent, loses jobs on restart
- **PostgreSQL as queue**: Works but not optimized for queue workload

**Trade-offs:**
- Pro: Proven, scalable, persistent
- Con: Additional dependency (Redis)

---

## Decision 13: Health Endpoint Without Authentication

**What was decided:** `/health` endpoint doesn't require API key

**Why:**
- Load balancers need unauthenticated health checks
- Standard practice for health endpoints
- No sensitive information exposed

**Alternatives considered:**
- **Require auth for health**: Breaks load balancer integration
- **Separate internal health endpoint**: More complex

**Trade-offs:**
- Pro: Standard, works with infrastructure
- Con: Reveals service is running (acceptable)

---

## Decision 14: Cross-Tenant IaC via Request Parameters

**What was decided:** Cross-tenant deployments configured via `target_tenant_id` in request

**Why:**
- Matches CLI option semantics
- Clear intent in API call
- Enables audit logging of cross-tenant operations
- Simple to implement (pass through to CLI)

**Alternatives considered:**
- **Separate endpoint for cross-tenant**: More endpoints without benefit
- **Infer from credentials**: Not explicit, risky

**Trade-offs:**
- Pro: Explicit, auditable, clear
- Con: None significant

---

## Decision 15: Version in URL Path (/v1/)

**What was decided:** API version in path (`/v1/jobs/scan`)

**Why:**
- Clear versioning strategy
- Easy to run multiple versions simultaneously
- Standard REST practice

**Alternatives considered:**
- **Header versioning**: Less visible, harder to test
- **No versioning**: Breaks clients on changes

**Trade-offs:**
- Pro: Clear, standard, testable
- Con: Path changes on major versions (acceptable)

---

## Future Decisions to Make

1. **Authentication beyond API keys**: OAuth2? JWT? mTLS?
2. **Rate limiting strategy**: Per-key? Global? Per-operation?
3. **Job result TTL**: When to expire old jobs?
4. **Multi-region deployment**: How to handle geo-distributed workers?
5. **Webhook callbacks**: Allow clients to register callback URLs for job completion?
6. **Batch operations**: Submit multiple jobs in one request?

---

## Pattern Applied: Decision Recording

This follows amplihack's decision recording pattern:
> Document significant decisions as: What was decided | Why | Alternatives considered

See `.claude/context/PATTERNS.md` for the pattern definition.
