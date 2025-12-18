# Module: ATG Service (REST API Server)

## Purpose

Provide REST API for remote execution of ATG operations with async job queuing, authentication, and multi-tenant isolation.

## Module Location

```
src/server/
├── __init__.py              # Public API exports
├── main.py                  # FastAPI application entry point
├── api/
│   ├── __init__.py
│   ├── routes.py            # API endpoint definitions
│   ├── models.py            # Pydantic request/response models
│   ├── auth.py              # API key authentication middleware
│   └── dependencies.py      # FastAPI dependency injection
├── jobs/
│   ├── __init__.py
│   ├── queue.py             # Redis-backed job queue
│   ├── executor.py          # Job execution logic
│   ├── storage.py           # Job result and artifact storage
│   └── worker.py            # Background job worker
├── config.py                # Server configuration
├── middleware.py            # Request logging, error handling
└── tests/
    ├── __init__.py
    ├── test_api.py
    ├── test_auth.py
    ├── test_jobs.py
    └── fixtures/
        └── test_data.py
```

## Public API (Studs)

### FastAPI Application

```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Azure Tenant Grapher Service",
    description="Remote execution service for ATG operations",
    version="1.0.0"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure per environment
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"]
)

# Include routers
from src.server.api.routes import router
app.include_router(router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    # Initialize job queue
    # Start background workers
    # Verify Neo4j connection

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    # Close job queue connections
    # Stop background workers
```

### API Endpoints

```python
# api/routes.py
from fastapi import APIRouter, Depends, BackgroundTasks
from src.server.api.auth import verify_api_key
from src.server.api.models import *

router = APIRouter()

@router.post("/scan", response_model=ScanJobResponse)
async def submit_scan_job(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
) -> ScanJobResponse:
    """
    Submit async scan job.

    Args:
        request: Scan job parameters
        background_tasks: FastAPI background tasks
        api_key: Validated API key

    Returns:
        ScanJobResponse with job_id

    Raises:
        HTTPException 401: Invalid API key
        HTTPException 422: Invalid request parameters
    """

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    api_key: str = Depends(verify_api_key)
) -> JobStatusResponse:
    """
    Get current job status.

    Args:
        job_id: Job identifier
        api_key: Validated API key

    Returns:
        JobStatusResponse with status, progress, error

    Raises:
        HTTPException 404: Job not found
    """

@router.get("/jobs/{job_id}/result", response_model=JobResultResponse)
async def get_job_result(
    job_id: str,
    api_key: str = Depends(verify_api_key)
) -> JobResultResponse:
    """
    Get completed job result.

    Args:
        job_id: Job identifier
        api_key: Validated API key

    Returns:
        JobResultResponse with result data

    Raises:
        HTTPException 404: Job not found
        HTTPException 409: Job not completed
    """

@router.get("/jobs/{job_id}/artifacts")
async def download_artifacts(
    job_id: str,
    api_key: str = Depends(verify_api_key)
) -> FileResponse:
    """
    Download job artifacts as zip file.

    Args:
        job_id: Job identifier
        api_key: Validated API key

    Returns:
        FileResponse with zip containing artifacts

    Raises:
        HTTPException 404: Artifacts not found
    """

@router.post("/generate-iac", response_model=IaCJobResponse)
async def submit_iac_generation_job(
    request: IaCGenerationRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
) -> IaCJobResponse:
    """
    Submit IaC generation job.

    Args:
        request: IaC generation parameters
        background_tasks: FastAPI background tasks
        api_key: Validated API key

    Returns:
        IaCJobResponse with job_id
    """

@router.post("/create-tenant", response_model=TenantJobResponse)
async def submit_tenant_creation_job(
    request: TenantCreationRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
) -> TenantJobResponse:
    """
    Submit tenant creation job.

    Args:
        request: Tenant creation parameters
        background_tasks: FastAPI background tasks
        api_key: Validated API key

    Returns:
        TenantJobResponse with job_id
    """

@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: str,
    api_key: str = Depends(verify_api_key)
) -> dict:
    """
    Cancel running job.

    Args:
        job_id: Job identifier
        api_key: Validated API key

    Returns:
        Success message

    Raises:
        HTTPException 404: Job not found
        HTTPException 409: Job already completed
    """

@router.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint (no authentication required).

    Returns:
        Status and version info
    """

@router.get("/metrics")
async def get_metrics(api_key: str = Depends(verify_api_key)) -> dict:
    """
    Get service metrics.

    Returns:
        Metrics data (job queue depth, success rate, etc.)
    """
```

### Request/Response Models

```python
# api/models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ScanRequest(BaseModel):
    """Scan job request."""
    tenant_id: str = Field(..., description="Azure tenant ID to scan")
    subscription_ids: Optional[List[str]] = Field(
        None,
        description="Specific subscriptions to scan (all if not provided)"
    )
    resource_limit: Optional[int] = Field(
        None,
        description="Maximum resources to discover (for testing)"
    )
    filter_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Resource filters (resource types, regions, tags)"
    )
    enable_llm_descriptions: bool = Field(
        False,
        description="Generate LLM descriptions for resources"
    )

class ScanJobResponse(BaseModel):
    """Scan job submission response."""
    job_id: str
    status: JobStatus
    created_at: datetime

class JobStatusResponse(BaseModel):
    """Job status response."""
    job_id: str
    status: JobStatus
    progress: Optional[float] = Field(None, ge=0.0, le=1.0)
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]
    current_step: Optional[str]

class JobResultResponse(BaseModel):
    """Job result response."""
    job_id: str
    status: JobStatus
    result: Dict[str, Any]
    completed_at: datetime
    duration_seconds: float

class IaCGenerationRequest(BaseModel):
    """IaC generation request."""
    tenant_id: str
    output_format: str = Field(..., regex="^(terraform|bicep|arm)$")
    resource_types: Optional[List[str]] = None
    resource_groups: Optional[List[str]] = None
    auto_import_existing: bool = False

class IaCJobResponse(BaseModel):
    """IaC job submission response."""
    job_id: str
    status: JobStatus
    created_at: datetime

class TenantCreationRequest(BaseModel):
    """Tenant creation request."""
    spec_content: str = Field(..., description="Tenant specification markdown")
    dry_run: bool = Field(False, description="Validate without deploying")

class TenantJobResponse(BaseModel):
    """Tenant creation job response."""
    job_id: str
    status: JobStatus
    created_at: datetime
```

### Authentication

```python
# api/auth.py
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.server.config import ATGServerConfig

security = HTTPBearer()
config = ATGServerConfig.from_env()

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    Verify API key from Authorization header.

    Args:
        credentials: HTTP bearer token

    Returns:
        Valid API key

    Raises:
        HTTPException 401: Invalid API key
    """
    api_key = credentials.credentials

    if api_key not in config.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return api_key
```

### Job Queue

```python
# jobs/queue.py
import redis.asyncio as redis
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class Job:
    """Job data structure."""
    job_id: str
    job_type: str
    parameters: Dict[str, Any]
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    progress: Optional[float] = None
    current_step: Optional[str] = None

class JobQueue:
    """Redis-backed async job queue."""

    def __init__(self, redis_url: str):
        """
        Initialize job queue with Redis connection.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        self._redis = await redis.from_url(
            self.redis_url,
            decode_responses=True
        )

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    async def enqueue(
        self,
        job_id: str,
        job_type: str,
        parameters: Dict[str, Any]
    ) -> Job:
        """
        Add job to queue.

        Args:
            job_id: Unique job identifier
            job_type: Type of job (scan, generate_iac, create_tenant)
            parameters: Job-specific parameters

        Returns:
            Created Job object
        """
        job = Job(
            job_id=job_id,
            job_type=job_type,
            parameters=parameters,
            status="pending",
            created_at=datetime.utcnow()
        )

        # Store job data
        await self._redis.hset(
            f"job:{job_id}",
            mapping={k: json.dumps(v, default=str) for k, v in asdict(job).items()}
        )

        # Add to queue
        await self._redis.rpush("job_queue", job_id)

        return job

    async def dequeue(self) -> Optional[Job]:
        """
        Get next job from queue (blocking).

        Returns:
            Next Job or None if queue is empty
        """
        # Blocking pop with timeout
        result = await self._redis.blpop("job_queue", timeout=5)
        if not result:
            return None

        _, job_id = result
        return await self.get_job(job_id)

    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job or None if not found
        """
        data = await self._redis.hgetall(f"job:{job_id}")
        if not data:
            return None

        # Deserialize
        job_dict = {k: json.loads(v) for k, v in data.items()}
        return Job(**job_dict)

    async def update_status(
        self,
        job_id: str,
        status: str,
        progress: Optional[float] = None,
        current_step: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Update job status.

        Args:
            job_id: Job identifier
            status: New status
            progress: Progress percentage (0.0 to 1.0)
            current_step: Current execution step
            error: Error message if failed
        """
        updates = {"status": json.dumps(status)}

        if progress is not None:
            updates["progress"] = json.dumps(progress)
        if current_step is not None:
            updates["current_step"] = json.dumps(current_step)
        if error is not None:
            updates["error"] = json.dumps(error)

        # Update timestamps
        if status == "running" and not await self._redis.hexists(f"job:{job_id}", "started_at"):
            updates["started_at"] = json.dumps(datetime.utcnow().isoformat())
        elif status in ["completed", "failed", "cancelled"]:
            updates["completed_at"] = json.dumps(datetime.utcnow().isoformat())

        await self._redis.hset(f"job:{job_id}", mapping=updates)

    async def store_result(
        self,
        job_id: str,
        result: Dict[str, Any]
    ) -> None:
        """
        Store job result.

        Args:
            job_id: Job identifier
            result: Result data
        """
        await self._redis.hset(
            f"job:{job_id}",
            "result",
            json.dumps(result, default=str)
        )

    async def get_queue_depth(self) -> int:
        """Get number of pending jobs."""
        return await self._redis.llen("job_queue")

    async def cleanup_old_jobs(self, max_age_days: int = 7) -> int:
        """
        Remove jobs older than max_age_days.

        Args:
            max_age_days: Maximum age in days

        Returns:
            Number of jobs removed
        """
        # Implementation: scan for old jobs and delete
        pass
```

### Job Executor

```python
# jobs/executor.py
import logging
from typing import Dict, Any, Optional
from src.azure_tenant_grapher import AzureTenantGrapher
from src.config_manager import AzureTenantGrapherConfig
from src.server.jobs.queue import JobQueue, Job

logger = logging.getLogger(__name__)

class JobExecutor:
    """Executes ATG operations as async jobs."""

    def __init__(
        self,
        job_queue: JobQueue,
        atg_config: AzureTenantGrapherConfig
    ):
        """
        Initialize job executor.

        Args:
            job_queue: Job queue instance
            atg_config: ATG configuration
        """
        self.queue = job_queue
        self.atg_config = atg_config
        self.grapher = AzureTenantGrapher(atg_config)

    async def execute_job(self, job: Job) -> None:
        """
        Execute a job based on its type.

        Args:
            job: Job to execute
        """
        try:
            logger.info(f"Starting job {job.job_id} (type: {job.job_type})")
            await self.queue.update_status(job.job_id, "running")

            if job.job_type == "scan":
                await self._execute_scan(job)
            elif job.job_type == "generate_iac":
                await self._execute_iac_generation(job)
            elif job.job_type == "create_tenant":
                await self._execute_tenant_creation(job)
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")

            logger.info(f"Job {job.job_id} completed successfully")

        except Exception as e:
            logger.exception(f"Job {job.job_id} failed: {str(e)}")
            await self.queue.update_status(
                job.job_id,
                "failed",
                error=str(e)
            )

    async def _execute_scan(self, job: Job) -> None:
        """Execute scan operation."""
        params = job.parameters

        def progress_callback(stats):
            """Update job progress."""
            progress = stats.get("processed", 0) / max(stats.get("total", 1), 1)
            asyncio.create_task(
                self.queue.update_status(
                    job.job_id,
                    "running",
                    progress=progress,
                    current_step=f"Processed {stats.get('processed')} resources"
                )
            )

        result = await self.grapher.build_graph(
            progress_callback=progress_callback,
            filter_config=params.get("filter_config")
        )

        await self.queue.store_result(job.job_id, result)
        await self.queue.update_status(job.job_id, "completed")

    async def _execute_iac_generation(self, job: Job) -> None:
        """Execute IaC generation."""
        params = job.parameters

        # Import IaC generation modules
        from src.iac.traverser import TerraformTraverser
        from src.iac.emitters.terraform_emitter import TerraformEmitter

        # Execute generation
        traverser = TerraformTraverser(self.grapher.session_manager)
        emitter = TerraformEmitter()

        await self.queue.update_status(
            job.job_id,
            "running",
            current_step="Generating IaC files"
        )

        # Generate files (save to temp location)
        output_dir = Path(f"/tmp/atg-jobs/{job.job_id}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # ... IaC generation logic ...

        result = {
            "files_generated": len(list(output_dir.glob("*.tf"))),
            "output_dir": str(output_dir)
        }

        await self.queue.store_result(job.job_id, result)
        await self.queue.update_status(job.job_id, "completed")

    async def _execute_tenant_creation(self, job: Job) -> None:
        """Execute tenant creation."""
        params = job.parameters

        # Import tenant creator
        from src.tenant_creator import TenantCreator

        creator = TenantCreator(self.atg_config)

        await self.queue.update_status(
            job.job_id,
            "running",
            current_step="Creating tenant resources"
        )

        # Execute creation
        result = await creator.create_from_spec(
            spec_content=params["spec_content"],
            dry_run=params.get("dry_run", False)
        )

        await self.queue.store_result(job.job_id, result)
        await self.queue.update_status(job.job_id, "completed")
```

### Background Worker

```python
# jobs/worker.py
import asyncio
import logging
from src.server.jobs.queue import JobQueue
from src.server.jobs.executor import JobExecutor

logger = logging.getLogger(__name__)

class BackgroundWorker:
    """Background worker that processes jobs from queue."""

    def __init__(
        self,
        job_queue: JobQueue,
        executor: JobExecutor,
        max_concurrent: int = 3
    ):
        """
        Initialize worker.

        Args:
            job_queue: Job queue instance
            executor: Job executor instance
            max_concurrent: Maximum concurrent jobs
        """
        self.queue = job_queue
        self.executor = executor
        self.max_concurrent = max_concurrent
        self._running = False
        self._tasks: set = set()

    async def start(self) -> None:
        """Start processing jobs."""
        self._running = True
        logger.info(f"Worker started (max_concurrent={self.max_concurrent})")

        while self._running:
            try:
                # Wait if at capacity
                while len(self._tasks) >= self.max_concurrent:
                    await asyncio.sleep(1)
                    self._cleanup_completed_tasks()

                # Get next job
                job = await self.queue.dequeue()
                if not job:
                    continue

                # Execute in background
                task = asyncio.create_task(self.executor.execute_job(job))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

            except Exception as e:
                logger.exception(f"Worker error: {str(e)}")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop worker and wait for current jobs."""
        logger.info("Worker stopping...")
        self._running = False

        # Wait for current jobs to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        logger.info("Worker stopped")

    def _cleanup_completed_tasks(self) -> None:
        """Remove completed tasks from set."""
        self._tasks = {task for task in self._tasks if not task.done()}
```

## Contract

### Inputs
- **HTTP Requests**: API endpoint calls with authentication
- **Job Parameters**: Tenant IDs, configuration options
- **Environment Config**: Target tenant, Azure credentials

### Outputs
- **Job IDs**: Unique identifiers for tracking
- **Status Updates**: Real-time job progress
- **Results**: Scan statistics, generated artifacts
- **Error Messages**: Detailed failure information

### Side Effects
- **Job Queue Operations**: Redis writes
- **Azure API Calls**: Resource discovery, deployments
- **Neo4j Operations**: Graph database writes
- **File System**: Artifact storage

### Dependencies
- **External Libraries**:
  - `fastapi`: Web framework
  - `redis`: Job queue backend
  - `uvicorn`: ASGI server
  - `azure-identity`: Azure authentication

- **Internal Dependencies**:
  - All existing ATG services (unchanged)
  - `src.config_manager`: Configuration
  - `src.azure_tenant_grapher`: Core functionality

## Implementation Notes

### Graceful Shutdown

```python
# main.py
import signal
import asyncio

worker: Optional[BackgroundWorker] = None

@app.on_event("startup")
async def startup_event():
    global worker

    # Initialize services
    job_queue = JobQueue(redis_url=config.redis_url)
    await job_queue.connect()

    executor = JobExecutor(job_queue, atg_config)
    worker = BackgroundWorker(job_queue, executor, config.max_concurrent_jobs)

    # Start worker in background
    asyncio.create_task(worker.start())

@app.on_event("shutdown")
async def shutdown_event():
    global worker

    if worker:
        await worker.stop()

# Handle SIGTERM for container orchestration
def handle_sigterm(*args):
    logger.info("Received SIGTERM, initiating shutdown")
    asyncio.create_task(shutdown_event())

signal.signal(signal.SIGTERM, handle_sigterm)
```

### Rate Limiting

```python
# middleware.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/scan")
@limiter.limit("10/minute")  # 10 scans per minute per IP
async def submit_scan_job(...):
    pass
```

## Test Requirements

### Unit Tests
- API endpoint tests with mocked dependencies
- Authentication tests
- Job queue operations
- Job executor logic

### Integration Tests
- Full request-response cycle
- Job execution with real ATG services
- Multi-worker concurrency
- Error recovery scenarios

### Load Tests
- Concurrent job submissions
- Queue depth under load
- Worker scaling behavior

## Security Considerations

- **API Key Rotation**: Support multiple keys simultaneously
- **Job Isolation**: Prevent cross-job data leakage
- **Resource Limits**: Prevent DoS via large requests
- **Audit Logging**: Log all authenticated operations

## Performance Considerations

- **Connection Pooling**: Neo4j and Redis connections
- **Worker Scaling**: Adjust `max_concurrent_jobs` based on resources
- **Job Timeout**: Kill jobs that exceed maximum duration
- **Result Expiration**: Auto-delete old job results

## Monitoring

- **Health Endpoint**: `/health` for liveness probes
- **Metrics Endpoint**: `/metrics` for Prometheus
- **Structured Logging**: JSON logs for aggregation
- **Error Tracking**: Integrate with Sentry or similar
