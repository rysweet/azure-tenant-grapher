# Phase 2 Quick Start Guide

**Phase**: Phase 2 (REST API & WebSocket)
**Status**: Complete - API structure implemented, ready for Phase 3 execution layer

## Starting the Server

```bash
# Development mode (auto-reload)
uv run uvicorn src.remote.server.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uv run uvicorn src.remote.server.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Example API Calls

### Health Check (No Auth)

```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "neo4j_status": "connected",
  "environment": "dev"
}
```

### Submit Scan Job (Requires Auth)

```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Authorization: Bearer atg_dev_YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345678-1234-1234-1234-123456789abc",
    "resource_limit": 1000,
    "generate_spec": false,
    "visualize": false
  }'
```

Response (202 Accepted):
```json
{
  "job_id": "scan-a1b2c3d4",
  "status": "queued",
  "created_at": "2025-12-09T10:30:00Z",
  "websocket_url": "ws://localhost:8000/ws/progress/scan-a1b2c3d4"
}
```

### Generate IaC (Requires Auth)

```bash
curl -X POST http://localhost:8000/api/v1/generate-iac \
  -H "Authorization: Bearer atg_dev_YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345678-1234-1234-1234-123456789abc",
    "format": "terraform",
    "auto_import_existing": false
  }'
```

### WebSocket Progress Streaming

**JavaScript Example:**
```javascript
const apiKey = "atg_dev_YOUR_API_KEY_HERE";
const jobId = "scan-a1b2c3d4";
const ws = new WebSocket(`ws://localhost:8000/ws/progress/${jobId}?api_key=${apiKey}`);

ws.onopen = () => {
  console.log("Connected to progress stream");
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch(message.type) {
    case 'progress':
      console.log(`Progress: ${message.progress}% - ${message.message}`);
      break;
    case 'completion':
      console.log("Job completed:", message.result);
      ws.close();
      break;
    case 'error':
      console.error("Job error:", message.error_message);
      ws.close();
      break;
    case 'log':
      console.log(`[${message.level}] ${message.message}`);
      break;
  }
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = () => {
  console.log("Disconnected from progress stream");
};
```

**Python Example:**
```python
import asyncio
import websockets
import json

async def stream_progress(job_id, api_key):
    uri = f"ws://localhost:8000/ws/progress/{job_id}?api_key={api_key}"

    async with websockets.connect(uri) as websocket:
        print("Connected to progress stream")

        async for message in websocket:
            data = json.loads(message)

            if data['type'] == 'progress':
                print(f"Progress: {data['progress']}% - {data['message']}")
            elif data['type'] == 'completion':
                print("Job completed:", data['result'])
                break
            elif data['type'] == 'error':
                print("Job error:", data['error_message'])
                break
            elif data['type'] == 'log':
                print(f"[{data['level']}] {data['message']}")

# Run
asyncio.run(stream_progress("scan-a1b2c3d4", "atg_dev_YOUR_API_KEY_HERE"))
```

## Environment Variables

Create a `.env` file:

```bash
# Server Configuration
ATG_SERVER_HOST=0.0.0.0
ATG_SERVER_PORT=8000
ATG_SERVER_WORKERS=4

# Authentication
ATG_API_KEYS="atg_dev_key1,atg_dev_key2"  # Comma-separated

# Target Tenant
ATG_TARGET_TENANT_ID=12345678-1234-1234-1234-123456789abc

# Azure Authentication
ATG_USE_MANAGED_IDENTITY=true

# Operational Limits
ATG_MAX_CONCURRENT_OPS=3

# Environment
ENVIRONMENT=dev  # dev, integration, or production

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=YourSecurePassword123!@#
NEO4J_DEV_POOL_SIZE=50
NEO4J_INTEGRATION_POOL_SIZE=30
```

## Testing with curl

### Valid Request
```bash
# Generate API key for testing (in dev mode)
API_KEY="atg_dev_$(openssl rand -hex 32)"

# Make authenticated request
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "12345678-1234-1234-1234-123456789abc"}'
```

### Invalid Tenant ID (400 Bad Request)
```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "invalid-id"}'
```

Response:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid tenant_id: tenant_id must be a valid UUID"
  }
}
```

### Missing Authorization (401 Unauthorized)
```bash
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "12345678-1234-1234-1234-123456789abc"}'
```

Response:
```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Missing Authorization header"
  }
}
```

## Phase 2 Limitations

**What Works:**
- ✅ All API endpoints accept requests
- ✅ Request validation (Pydantic)
- ✅ Authentication (API key)
- ✅ Error handling (proper status codes)
- ✅ WebSocket connections
- ✅ Health checks

**What's Stubbed (Phase 3 will implement):**
- ⏳ Actual operation execution (scan, generate-iac)
- ⏳ Job status tracking in Neo4j
- ⏳ Real progress updates via WebSocket
- ⏳ File generation and download
- ⏳ Operation cancellation

**Current Behavior:**
- All job submissions return 202 Accepted with job_id
- Status queries return 404 Not Found (no jobs stored yet)
- WebSocket connections work but receive no messages (no execution yet)

## Next Steps (Phase 3)

Phase 3 will add:
1. Operation execution using existing ATG services
2. Job storage in Neo4j
3. Real-time progress tracking
4. File generation and storage
5. Background task execution

## Troubleshooting

### "Connection manager not initialized"
- Server hasn't started yet
- Check environment variables are set (NEO4J_URI, NEO4J_PASSWORD, etc.)

### "Invalid API key"
- API key doesn't match environment prefix
- For dev: Use keys starting with `atg_dev_`
- For production: Use keys starting with `atg_production_`

### "Database connection unavailable"
- Neo4j container not running
- Check `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` in `.env`
- Verify Neo4j is accessible: `docker ps | grep neo4j`

### WebSocket connection fails
- Check API key is in query parameter: `?api_key=...`
- Verify job_id exists (Phase 3 will track jobs)
- Check browser console for detailed error

## Development Workflow

1. **Start Neo4j** (if not running):
   ```bash
   docker run -d --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/YourSecurePassword123!@# \
     neo4j:5.12
   ```

2. **Configure environment**: Copy `.env.example` to `.env` and update values

3. **Start server**: `uv run uvicorn src.remote.server.main:app --reload`

4. **Test endpoints**: Visit http://localhost:8000/docs

5. **Monitor logs**: Server logs show all requests and errors

## API Reference

See `docs/remote-mode/API_REFERENCE.md` for complete API documentation including:
- All endpoints with parameters
- Request/response schemas
- Error codes
- Rate limits (Phase 3)
- Pagination (Phase 3)

---

**Ready for Phase 3!** The API structure is complete and ready for operation execution implementation. 🏴‍☠️
