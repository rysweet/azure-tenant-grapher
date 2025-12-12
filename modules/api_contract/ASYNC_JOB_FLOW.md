# Async Job Flow Architecture

This document details the async job pattern used throughout the ATG Remote API.

## Overview

All long-running operations (scan, generate-iac, etc.) use an async job pattern to handle operations that can take 20+ minutes without blocking HTTP connections.

## Job Lifecycle

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ 1. POST /v1/jobs/scan
       │    {tenant_id: "..."}
       ▼
┌─────────────────┐
│   API Server    │
│                 │
│  ┌───────────┐  │
│  │Job Queue  │  │
│  │(Redis)    │  │
│  └───────────┘  │
└────┬────────────┘
     │
     │ 2. Return job_id
     │    status: "pending"
     ▼
┌─────────────┐
│   Client    │
│             │
│  Polls or   │
│  Streams    │
└──────┬──────┘
       │
       │ 3a. GET /v1/jobs/{id}      (polling)
       │     Every 30 seconds
       │
       │ 3b. GET /v1/jobs/{id}/progress  (streaming)
       │     SSE connection
       ▼
┌─────────────────┐
│   API Server    │
│                 │
│  Returns status │
│  & progress     │
└─────────────────┘
       ▲
       │
       │ 4. Worker processes job
       │
┌──────┴──────┐
│   Worker    │
│   (Celery)  │
│             │
│  Executes   │
│  CLI command│
│             │
│  Publishes  │
│  progress   │
└──────┬──────┘
       │
       │ 5. Job completes
       │    Status: "completed"
       │    Results stored
       ▼
┌─────────────┐
│   Client    │
│             │
│  Polls or   │
│  gets event │
└──────┬──────┘
       │
       │ 6. GET /v1/jobs/{id}/results
       │
       ▼
┌─────────────────┐
│   API Server    │
│                 │
│  Returns result │
│  + file URLs    │
└─────────────────┘
       │
       │ 7. GET /v1/files/{file_id}
       ▼
┌─────────────┐
│   Client    │
│             │
│  Downloads  │
│  files      │
└─────────────┘
```

## Detailed Flow

### Phase 1: Job Submission

**Client → API Server**

```http
POST /v1/jobs/scan
X-API-Key: api-key-here
Content-Type: application/json

{
  "tenant_id": "12345678-1234-1234-1234-123456789abc",
  "max_llm_threads": 5,
  "generate_spec": true
}
```

**API Server Processing:**
1. Authenticate API key
2. Validate request schema
3. Generate job_id (UUID)
4. Store job metadata in database
5. Enqueue job to worker queue (Redis)
6. Return response immediately

**Response:**
```http
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "status_url": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000",
  "progress_url": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000/progress"
}
```

**Timing:** < 100ms

### Phase 2: Job Queuing

**Job Queue (Redis):**
```
RPUSH job_queue {
  "job_id": "550e8400-...",
  "operation": "scan",
  "params": {...},
  "created_at": "2025-12-09T10:00:00Z"
}
```

**Job Status (Database):**
```sql
INSERT INTO jobs (id, operation, status, created_at, params)
VALUES ('550e8400-...', 'scan', 'pending', NOW(), {...});
```

### Phase 3: Status Monitoring

**Option A: Polling (Simple)**

Client polls every 30 seconds:

```http
GET /v1/jobs/550e8400-e29b-41d4-a716-446655440000
X-API-Key: api-key-here
```

**Response (Running):**
```json
{
  "job_id": "550e8400-...",
  "operation": "scan",
  "status": "running",
  "progress": 45.5,
  "message": "Processing resource group 5 of 11",
  "created_at": "2025-12-09T10:00:00Z",
  "started_at": "2025-12-09T10:00:01Z",
  "completed_at": null
}
```

**Timing:** 30s intervals, minimal server load

**Option B: Server-Sent Events (Real-time)**

Client opens SSE connection:

```http
GET /v1/jobs/550e8400-e29b-41d4-a716-446655440000/progress
X-API-Key: api-key-here
Accept: text/event-stream
```

**Response (Stream):**
```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

event: progress
data: {"job_id": "550e8400-...", "status": "running", "progress": 10.0, "message": "Discovered 3 subscriptions"}

event: progress
data: {"job_id": "550e8400-...", "status": "running", "progress": 25.0, "message": "Processing resource group 1 of 11"}

event: progress
data: {"job_id": "550e8400-...", "status": "running", "progress": 45.0, "message": "Processing resource group 5 of 11"}

event: complete
data: {"job_id": "550e8400-...", "status": "completed"}
```

**Timing:** Real-time, ~1 update every 10-30 seconds

### Phase 4: Worker Processing

**Worker picks up job from queue:**

```python
# Celery worker
@celery_app.task
def process_scan_job(job_id, params):
    # Update status to "running"
    update_job_status(job_id, "running", progress=0)

    # Execute CLI command
    result = subprocess.run([
        "atg", "scan",
        "--tenant-id", params["tenant_id"],
        "--max-llm-threads", str(params["max_llm_threads"]),
        "--generate-spec" if params.get("generate_spec") else ""
    ], capture_output=True, text=True)

    # Parse progress from CLI output
    for line in result.stdout.split('\n'):
        if progress_info := parse_progress(line):
            update_job_status(
                job_id,
                "running",
                progress=progress_info["percent"],
                message=progress_info["message"]
            )
            # Publish to SSE stream
            publish_progress_event(job_id, progress_info)

    # Store results
    store_job_results(job_id, {
        "resources_scanned": result.stats["resources"],
        "relationships_created": result.stats["relationships"],
        "duration_seconds": result.duration
    })

    # Store generated files
    if params.get("generate_spec"):
        file_id = store_file(result.spec_file)
        add_job_file(job_id, file_id, "tenant_spec.md")

    # Update status to "completed"
    update_job_status(job_id, "completed", progress=100)
```

**Timing:** 1-30+ minutes depending on operation

### Phase 5: Results Retrieval

**Client checks status, sees "completed", fetches results:**

```http
GET /v1/jobs/550e8400-e29b-41d4-a716-446655440000/results
X-API-Key: api-key-here
```

**Response:**
```json
{
  "job_id": "550e8400-...",
  "operation": "scan",
  "status": "completed",
  "result": {
    "resources_scanned": 1024,
    "relationships_created": 3456,
    "duration_seconds": 1364,
    "subscriptions": 3,
    "resource_groups": 11
  },
  "files": [
    {
      "file_id": "abc123def456",
      "filename": "tenant_spec_20251209_102245.md",
      "mime_type": "text/markdown",
      "size": 45678,
      "download_url": "/v1/files/abc123def456"
    }
  ]
}
```

### Phase 6: File Download

**Client downloads generated files:**

```http
GET /v1/files/abc123def456
X-API-Key: api-key-here
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: text/markdown
Content-Disposition: attachment; filename="tenant_spec_20251209_102245.md"
Content-Length: 45678

# Tenant Specification
...
```

## State Machine

```
┌─────────┐
│ pending │
└────┬────┘
     │
     │ Worker picks up job
     ▼
┌─────────┐
│ running │──────────┐
└────┬────┘          │
     │               │ Error occurs
     │               ▼
     │          ┌────────┐
     │          │ failed │
     │          └────────┘
     │
     │ Job completes
     ▼
┌───────────┐
│ completed │
└───────────┘

     ▲
     │
     │ User cancels
     │
┌───────────┐
│ cancelled │
└───────────┘
```

**Valid transitions:**
- pending → running
- pending → cancelled
- running → completed
- running → failed
- running → cancelled

**Invalid transitions:**
- completed → running
- failed → completed

## Error Handling

### Job Submission Errors

**Invalid request:**
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Missing required field: tenant_id",
    "details": {
      "field": "tenant_id",
      "expected": "UUID string"
    }
  }
}
```

**Authentication error:**
```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": {
    "code": "INVALID_API_KEY",
    "message": "API key is invalid or expired"
  }
}
```

### Job Processing Errors

**Worker updates job status:**
```python
update_job_status(
    job_id,
    "failed",
    error="Azure authentication failed: Invalid tenant ID"
)
```

**Client retrieves error:**
```http
GET /v1/jobs/{job_id}
```

**Response:**
```json
{
  "job_id": "550e8400-...",
  "operation": "scan",
  "status": "failed",
  "error": "Azure authentication failed: Invalid tenant ID",
  "created_at": "2025-12-09T10:00:00Z",
  "started_at": "2025-12-09T10:00:01Z",
  "completed_at": "2025-12-09T10:00:15Z"
}
```

## Progress Updates Architecture

### Progress Event Publishing

**Worker → Redis Pub/Sub:**
```python
def publish_progress_event(job_id, progress_info):
    redis_client.publish(
        f"job:{job_id}:progress",
        json.dumps({
            "job_id": job_id,
            "status": "running",
            "progress": progress_info["percent"],
            "message": progress_info["message"],
            "timestamp": datetime.now().isoformat()
        })
    )
```

**API Server → SSE Clients:**
```python
@app.get("/v1/jobs/{job_id}/progress")
async def stream_progress(job_id: str):
    async def event_generator():
        # Subscribe to Redis pub/sub
        pubsub = redis_client.pubsub()
        pubsub.subscribe(f"job:{job_id}:progress")

        for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                yield f"event: progress\ndata: {json.dumps(data)}\n\n"

                if data["status"] in ["completed", "failed"]:
                    break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

## Scalability Considerations

### Horizontal Scaling

**API Servers:**
- Stateless, can scale horizontally
- Load balancer distributes requests
- Shared Redis and database

**Workers:**
- Scale based on job queue depth
- Each worker processes one job at a time
- Auto-scale based on queue length

### Performance Metrics

**Job submission:** < 100ms
**Status check:** < 50ms
**SSE connection:** < 100ms initial, real-time updates
**Worker processing:** 1-30+ minutes (operation-dependent)
**Results retrieval:** < 200ms
**File download:** Network-limited

## Implementation Technologies

**Recommended stack:**
- **API Server:** FastAPI (Python async)
- **Job Queue:** Celery + Redis
- **Database:** PostgreSQL (job metadata)
- **File Storage:** Azure Blob Storage or S3
- **Progress Events:** Redis Pub/Sub
- **Monitoring:** Prometheus + Grafana

## Example Client Implementation

```python
import requests
import time
from typing import Optional

class ATGClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}

    def submit_scan(self, tenant_id: str, **kwargs) -> str:
        """Submit scan job, return job_id"""
        response = requests.post(
            f"{self.base_url}/jobs/scan",
            headers=self.headers,
            json={"tenant_id": tenant_id, **kwargs}
        )
        response.raise_for_status()
        return response.json()["job_id"]

    def wait_for_completion(
        self,
        job_id: str,
        poll_interval: int = 30
    ) -> dict:
        """Poll until job completes"""
        while True:
            status = self.get_job_status(job_id)
            if status["status"] in ["completed", "failed", "cancelled"]:
                return status
            time.sleep(poll_interval)

    def stream_progress(self, job_id: str):
        """Stream progress via SSE"""
        response = requests.get(
            f"{self.base_url}/jobs/{job_id}/progress",
            headers=self.headers,
            stream=True
        )

        for line in response.iter_lines():
            if line.startswith(b"data:"):
                data = json.loads(line[5:])
                yield data
                if data["status"] in ["completed", "failed"]:
                    break

    def get_results(self, job_id: str) -> dict:
        """Get job results"""
        response = requests.get(
            f"{self.base_url}/jobs/{job_id}/results",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def download_file(self, file_id: str, output_path: str):
        """Download generated file"""
        response = requests.get(
            f"{self.base_url}/files/{file_id}",
            headers=self.headers,
            stream=True
        )
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
```

**Usage:**
```python
client = ATGClient("https://api.atg.example.com/v1", "your-api-key")

# Submit job
job_id = client.submit_scan(
    tenant_id="12345678-...",
    generate_spec=True
)

# Stream progress
for progress in client.stream_progress(job_id):
    print(f"{progress['progress']:.1f}% - {progress['message']}")

# Get results
results = client.get_results(job_id)
print(f"Scanned {results['result']['resources_scanned']} resources")

# Download files
for file in results["files"]:
    client.download_file(file["file_id"], file["filename"])
```

## Monitoring and Observability

### Metrics to Track

**Job metrics:**
- Jobs submitted per minute
- Jobs completed per minute
- Average job duration by operation
- Job failure rate

**Queue metrics:**
- Queue depth
- Average queue wait time
- Worker utilization

**API metrics:**
- Request rate by endpoint
- Response time p50/p95/p99
- Error rate by status code

### Health Checks

```http
GET /v1/health

Response:
{
  "status": "healthy",
  "version": "1.0.0",
  "neo4j_status": "connected",
  "redis_status": "connected",
  "queue_depth": 5,
  "active_workers": 10
}
```

## Next Steps

1. Implement server with FastAPI
2. Set up Celery workers
3. Implement progress publishing
4. Add monitoring
5. Load test with real workloads
