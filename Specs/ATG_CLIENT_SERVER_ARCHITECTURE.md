# ATG Client-Server Architecture Specification

**Version**: 1.0
**Date**: 2025-12-09
**Status**: APPROVED FOR IMPLEMENTATION

## Executive Summary

This specification defines the architecture for transforming Azure Tenant Grapher (ATG) from a CLI-only local tool into a client-server system supporting both local and remote execution modes. The design preserves backward compatibility while adding enterprise deployment capabilities.

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER ENVIRONMENT                            │
│                                                                     │
│  ┌──────────────┐         ┌──────────────────────────────────┐   │
│  │   ATG CLI    │◄────────┤  Execution Mode Dispatcher       │   │
│  │   (Client)   │         │  • Local Mode (backward compat)  │   │
│  └──────┬───────┘         │  • Remote Mode (new)             │   │
│         │                 └──────────────────────────────────┘   │
│         │                                                         │
│         │ Local Mode: Direct execution                           │
│         │ Remote Mode: REST API calls                            │
│         │                                                         │
└─────────┼─────────────────────────────────────────────────────────┘
          │
          │ HTTPS + API Key
          │
┌─────────▼─────────────────────────────────────────────────────────┐
│                    AZURE CONTAINER ENVIRONMENT                     │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              ATG Service (FastAPI)                          │  │
│  │                                                             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │  REST API    │  │  Job Queue   │  │  Job Executor   │  │  │
│  │  │  Endpoints   │  │  (Redis)     │  │  (Workers)      │  │  │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘  │  │
│  │                                                             │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │         Existing ATG Core Services                   │  │  │
│  │  │  • AzureDiscoveryService                            │  │  │
│  │  │  • ResourceProcessingService                        │  │  │
│  │  │  • IaC Generation (Terraform/Bicep/ARM)            │  │  │
│  │  │  • Tenant Creator                                   │  │  │
│  │  │  • Threat Modeling                                  │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Neo4j Database Container                       │  │
│  │  • Graph storage for discovered resources                  │  │
│  │  • Multi-tenant isolation via DB namespacing               │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Azure Identity Integration                      │  │
│  │  • Managed Identity for target tenant access               │  │
│  │  • Service Principal authentication                         │  │
│  └─────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### 1.2 Three-Environment Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    GITHUB ACTIONS CI/CD                          │
│                                                                  │
│  main branch    ──►  Dev Environment    ──►  DefenderATEVET17   │
│  integration    ──►  Integration Env    ──►  Target Tenant A    │
│  prod branch    ──►  Production Env     ──►  Target Tenant B    │
└──────────────────────────────────────────────────────────────────┘

Each Environment:
  • Azure Container Instance (64GB RAM)
  • Separate Neo4j database
  • Environment-specific .env configuration
  • Isolated API key authentication
```

---

## 2. Component Specifications

### 2.1 CLI Client Module (NEW: `src/client/`)

**Purpose**: CLI client that supports both local and remote execution modes.

**Module Structure**:
```
src/client/
├── __init__.py              # Public API: RemoteClient
├── remote_client.py         # REST API client implementation
├── execution_dispatcher.py  # Mode detection and routing
├── config.py                # Client configuration
└── tests/
    ├── test_remote_client.py
    ├── test_dispatcher.py
    └── fixtures/
```

**Public API (Studs)**:
```python
# remote_client.py
class RemoteClient:
    """REST client for ATG service communication."""

    def __init__(
        self,
        service_url: str,
        api_key: str,
        timeout: int = 300
    ):
        """Initialize remote client with authentication."""
        pass

    async def submit_scan_job(
        self,
        tenant_id: str,
        config: Dict[str, Any]
    ) -> str:
        """Submit async scan job, returns job_id."""
        pass

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Poll job status."""
        pass

    async def get_job_result(self, job_id: str) -> Dict[str, Any]:
        """Retrieve completed job results."""
        pass

    async def download_artifacts(
        self,
        job_id: str,
        output_dir: Path
    ) -> None:
        """Download generated IaC artifacts."""
        pass

# execution_dispatcher.py
class ExecutionDispatcher:
    """Routes commands to local or remote execution."""

    def __init__(self, config: ATGClientConfig):
        """Initialize with client configuration."""
        pass

    async def execute_scan(
        self,
        tenant_id: str,
        **kwargs
    ) -> ScanResult:
        """Execute scan in appropriate mode."""
        pass

    def is_remote_mode(self) -> bool:
        """Check if remote mode is configured."""
        pass
```

**Contract**:
- **Inputs**: Service URL, API key, command parameters
- **Outputs**: Job IDs, status objects, result artifacts
- **Side Effects**: Network requests to remote service
- **Dependencies**: `httpx`, `pydantic`, existing CLI commands

---

### 2.2 ATG Service Module (NEW: `src/server/`)

**Purpose**: FastAPI server exposing ATG functionality via REST API.

**Module Structure**:
```
src/server/
├── __init__.py              # Public API: ATGService
├── main.py                  # FastAPI application entry point
├── api/
│   ├── __init__.py
│   ├── routes.py            # API endpoint definitions
│   ├── models.py            # Pydantic request/response models
│   └── auth.py              # API key authentication
├── jobs/
│   ├── __init__.py
│   ├── queue.py             # Redis-backed job queue
│   ├── executor.py          # Job execution logic
│   └── storage.py           # Job result storage
├── config.py                # Server configuration
└── tests/
    ├── test_api.py
    ├── test_jobs.py
    └── fixtures/
```

**Public API (Studs)**:
```python
# API Endpoints (routes.py)
@app.post("/api/v1/scan")
async def submit_scan_job(
    request: ScanRequest,
    api_key: str = Depends(verify_api_key)
) -> ScanJobResponse:
    """Submit async scan job."""
    pass

@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    api_key: str = Depends(verify_api_key)
) -> JobStatusResponse:
    """Get job status."""
    pass

@app.get("/api/v1/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    api_key: str = Depends(verify_api_key)
) -> JobResultResponse:
    """Get job result when complete."""
    pass

@app.get("/api/v1/jobs/{job_id}/artifacts")
async def download_artifacts(
    job_id: str,
    api_key: str = Depends(verify_api_key)
) -> FileResponse:
    """Download job artifacts (IaC files)."""
    pass

@app.post("/api/v1/generate-iac")
async def submit_iac_generation_job(
    request: IaCGenerationRequest,
    api_key: str = Depends(verify_api_key)
) -> IaCJobResponse:
    """Submit IaC generation job."""
    pass

@app.post("/api/v1/create-tenant")
async def submit_tenant_creation_job(
    request: TenantCreationRequest,
    api_key: str = Depends(verify_api_key)
) -> TenantJobResponse:
    """Submit tenant creation job."""
    pass

# Job Executor (executor.py)
class JobExecutor:
    """Executes ATG operations as async jobs."""

    async def execute_scan(
        self,
        job_id: str,
        tenant_id: str,
        config: Dict[str, Any]
    ) -> None:
        """Execute scan operation, update job status."""
        pass

    async def execute_iac_generation(
        self,
        job_id: str,
        config: Dict[str, Any]
    ) -> None:
        """Execute IaC generation."""
        pass
```

**Contract**:
- **Inputs**: HTTP requests with authentication, job parameters
- **Outputs**: Job IDs, status updates, result data
- **Side Effects**: Job queue operations, database writes, artifact storage
- **Dependencies**: `fastapi`, `redis`, existing ATG services, `azure-identity`

---

### 2.3 Job Queue Module (`src/server/jobs/`)

**Purpose**: Async job queue for long-running operations.

**Public API (Studs)**:
```python
class JobQueue:
    """Redis-backed async job queue."""

    def __init__(self, redis_url: str):
        """Initialize with Redis connection."""
        pass

    async def enqueue(
        self,
        job_id: str,
        job_type: JobType,
        parameters: Dict[str, Any]
    ) -> None:
        """Add job to queue."""
        pass

    async def dequeue(self) -> Optional[Job]:
        """Get next job from queue."""
        pass

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[float] = None
    ) -> None:
        """Update job status."""
        pass

    async def get_status(self, job_id: str) -> JobStatus:
        """Get current job status."""
        pass

    async def store_result(
        self,
        job_id: str,
        result: Dict[str, Any]
    ) -> None:
        """Store job result."""
        pass

class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    """Job data structure."""
    job_id: str
    job_type: JobType
    parameters: Dict[str, Any]
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
```

**Contract**:
- **Inputs**: Job parameters, status updates
- **Outputs**: Job objects, status information
- **Side Effects**: Redis operations
- **Dependencies**: `redis-py`, `pydantic`

---

### 2.4 Configuration Module Updates

**Changes to `src/config_manager.py`**:

```python
@dataclass
class ATGClientConfig:
    """Client-side configuration for remote mode."""

    # Remote mode settings
    remote_mode: bool = False
    service_url: Optional[str] = None
    api_key: Optional[str] = None

    # Timeout settings
    request_timeout: int = 300
    job_poll_interval: int = 5

    @classmethod
    def from_env(cls) -> "ATGClientConfig":
        """Load configuration from environment."""
        return cls(
            remote_mode=os.getenv("ATG_REMOTE_MODE", "false").lower() == "true",
            service_url=os.getenv("ATG_SERVICE_URL"),
            api_key=os.getenv("ATG_API_KEY"),
            request_timeout=int(os.getenv("ATG_REQUEST_TIMEOUT", "300")),
            job_poll_interval=int(os.getenv("ATG_JOB_POLL_INTERVAL", "5"))
        )

    def validate(self) -> None:
        """Validate remote mode configuration."""
        if self.remote_mode:
            if not self.service_url:
                raise ValueError("ATG_SERVICE_URL required for remote mode")
            if not self.api_key:
                raise ValueError("ATG_API_KEY required for remote mode")

@dataclass
class ATGServerConfig:
    """Server-side configuration."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Authentication
    api_keys: List[str] = field(default_factory=list)

    # Job queue
    redis_url: str = "redis://localhost:6379"
    max_concurrent_jobs: int = 3

    # Target tenant configuration
    target_tenant_id: str = ""
    target_subscription_id: str = ""

    # Azure authentication
    use_managed_identity: bool = True
    service_principal_client_id: Optional[str] = None
    service_principal_secret: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ATGServerConfig":
        """Load server configuration from environment."""
        return cls(
            host=os.getenv("ATG_SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("ATG_SERVER_PORT", "8000")),
            workers=int(os.getenv("ATG_SERVER_WORKERS", "4")),
            api_keys=os.getenv("ATG_API_KEYS", "").split(","),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            max_concurrent_jobs=int(os.getenv("ATG_MAX_CONCURRENT_JOBS", "3")),
            target_tenant_id=os.getenv("ATG_TARGET_TENANT_ID", ""),
            target_subscription_id=os.getenv("ATG_TARGET_SUBSCRIPTION_ID", ""),
            use_managed_identity=os.getenv("ATG_USE_MANAGED_IDENTITY", "true").lower() == "true",
            service_principal_client_id=os.getenv("AZURE_CLIENT_ID"),
            service_principal_secret=os.getenv("AZURE_CLIENT_SECRET")
        )
```

---

## 3. Data Flow Specifications

### 3.1 Remote Scan Operation Flow

```
┌──────────┐                                    ┌──────────────┐
│ CLI User │                                    │  ATG Service │
└────┬─────┘                                    └──────┬───────┘
     │                                                 │
     │ 1. atg scan --tenant-id X                      │
     │    (detects remote mode from .env)             │
     ├────────────────────────────────────────────────►│
     │ POST /api/v1/scan                              │
     │ {tenant_id: X, config: {...}}                  │
     │                                                 │
     │◄────────────────────────────────────────────────┤
     │ 2. Response: {job_id: "abc123"}                │
     │                                                 │
     │                                                 │ 3. Enqueue job
     │                                                 │    in Redis
     │                                                 ├──────┐
     │                                                 │      │
     │                                                 │◄─────┘
     │                                                 │
     │ 4. Poll status every 5 seconds                 │
     ├────────────────────────────────────────────────►│
     │ GET /api/v1/jobs/abc123                        │
     │                                                 │
     │◄────────────────────────────────────────────────┤
     │ Response: {status: "running", progress: 45%}   │
     │                                                 │
     │                                                 │ 5. Worker executes
     │                                                 │    AzureDiscoveryService
     │                                                 │    ResourceProcessingService
     │                                                 ├──────┐
     │                                                 │      │
     │                                                 │◄─────┘
     │                                                 │
     │ 6. Poll again                                  │
     ├────────────────────────────────────────────────►│
     │ GET /api/v1/jobs/abc123                        │
     │                                                 │
     │◄────────────────────────────────────────────────┤
     │ Response: {status: "completed"}                │
     │                                                 │
     │                                                 │
     │ 7. Retrieve results                            │
     ├────────────────────────────────────────────────►│
     │ GET /api/v1/jobs/abc123/result                 │
     │                                                 │
     │◄────────────────────────────────────────────────┤
     │ Response: {resources: 902, success: true}      │
     │                                                 │
     │ 8. Display results to user                     │
     │                                                 │
```

### 3.2 IaC Generation Flow

```
User: atg generate-iac --remote
  ↓
CLI detects remote mode
  ↓
POST /api/v1/generate-iac
  ↓
Service enqueues job
  ↓
Worker executes:
  • Query Neo4j for resources
  • Run IaC traverser
  • Generate Terraform/Bicep files
  • Store artifacts in blob storage
  ↓
CLI polls for completion
  ↓
CLI downloads artifacts
  ↓
Files saved to local directory
```

---

## 4. Integration Points with Existing ATG

### 4.1 Existing Services Integration

**Zero Changes Required** to existing core services:
- `AzureDiscoveryService`: Used as-is by job executor
- `ResourceProcessingService`: Used as-is
- `TenantSpecificationService`: Used as-is
- IaC emitters (Terraform/Bicep/ARM): Used as-is

**Integration Pattern**:
```python
# src/server/jobs/executor.py
class JobExecutor:
    def __init__(self, config: ATGServerConfig):
        # Initialize existing ATG services
        self.atg_config = AzureTenantGrapherConfig.from_env()
        self.grapher = AzureTenantGrapher(self.atg_config)

    async def execute_scan(self, job_id: str, tenant_id: str, config: Dict[str, Any]):
        """Execute scan using existing ATG services."""
        try:
            # Update job status
            await self.queue.update_status(job_id, JobStatus.RUNNING)

            # Use existing ATG build_graph method
            result = await self.grapher.build_graph(
                progress_callback=lambda stats: self._update_progress(job_id, stats),
                filter_config=config.get("filter_config")
            )

            # Store result
            await self.queue.store_result(job_id, result)
            await self.queue.update_status(job_id, JobStatus.COMPLETED)

        except Exception as e:
            await self.queue.update_status(job_id, JobStatus.FAILED)
            raise
```

### 4.2 CLI Integration Points

**Modified CLI commands** (`scripts/cli.py`):

```python
@app.command()
def scan(
    tenant_id: str,
    remote: bool = typer.Option(False, "--remote", help="Use remote service"),
    # ... existing parameters
):
    """Scan Azure tenant resources (local or remote)."""

    # Initialize execution dispatcher
    client_config = ATGClientConfig.from_env()
    client_config.remote_mode = remote or client_config.remote_mode

    dispatcher = ExecutionDispatcher(client_config)

    # Dispatcher handles local vs remote execution
    result = asyncio.run(dispatcher.execute_scan(
        tenant_id=tenant_id,
        # ... pass other parameters
    ))

    # Display results (same for both modes)
    display_scan_results(result)
```

**Backward Compatibility**:
- Default behavior unchanged (local mode)
- Remote mode opt-in via `--remote` flag or `ATG_REMOTE_MODE=true`
- All existing CLI commands work exactly as before when not in remote mode

---

## 5. Deployment Architecture

### 5.1 Azure Container Infrastructure

**Container Specification**:
```yaml
# Azure Container Instance spec
resource "azurerm_container_group" "atg_service" {
  name                = "atg-service-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"

  container {
    name   = "atg-api"
    image  = "ghcr.io/yourorg/atg:${var.version}"
    cpu    = "4"
    memory = "64"

    ports {
      port     = 8000
      protocol = "TCP"
    }

    environment_variables = {
      ATG_SERVER_HOST              = "0.0.0.0"
      ATG_SERVER_PORT              = "8000"
      ATG_TARGET_TENANT_ID         = var.target_tenant_id
      ATG_USE_MANAGED_IDENTITY     = "true"
      REDIS_URL                    = "redis://redis-cache:6379"
      NEO4J_URI                    = "bolt://neo4j:7687"
    }

    secure_environment_variables = {
      ATG_API_KEYS    = var.api_keys
      NEO4J_PASSWORD  = var.neo4j_password
    }
  }

  container {
    name   = "neo4j"
    image  = "neo4j:5.15-community"
    cpu    = "2"
    memory = "32"

    ports {
      port     = 7687
      protocol = "TCP"
    }

    volumes {
      name                 = "neo4j-data"
      mount_path           = "/data"
      storage_account_name = var.storage_account_name
      storage_account_key  = var.storage_account_key
      share_name          = "neo4j-data-${var.environment}"
    }
  }

  container {
    name   = "redis"
    image  = "redis:7-alpine"
    cpu    = "1"
    memory = "4"

    ports {
      port     = 6379
      protocol = "TCP"
    }
  }

  identity {
    type = "SystemAssigned"
  }
}
```

### 5.2 Three-Environment Setup

**Environment Configuration Matrix**:

| Environment  | Branch       | Target Tenant       | Container Size | Neo4j DB        |
|-------------|--------------|---------------------|----------------|-----------------|
| Dev         | main         | DefenderATEVET17    | 64GB RAM       | atg-dev-db      |
| Integration | integration  | Target Tenant A     | 64GB RAM       | atg-int-db      |
| Production  | prod         | Target Tenant B     | 64GB RAM       | atg-prod-db     |

**GitHub Actions Workflow** (`.github/workflows/deploy-service.yml`):
```yaml
name: Deploy ATG Service

on:
  push:
    branches: [main, integration, prod]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set environment based on branch
        id: set-env
        run: |
          if [[ "${{ github.ref }}" == "refs/heads/main" ]]; then
            echo "ENV=dev" >> $GITHUB_OUTPUT
            echo "TENANT_ID=${{ secrets.DEV_TENANT_ID }}" >> $GITHUB_OUTPUT
          elif [[ "${{ github.ref }}" == "refs/heads/integration" ]]; then
            echo "ENV=integration" >> $GITHUB_OUTPUT
            echo "TENANT_ID=${{ secrets.INT_TENANT_ID }}" >> $GITHUB_OUTPUT
          elif [[ "${{ github.ref }}" == "refs/heads/prod" ]]; then
            echo "ENV=production" >> $GITHUB_OUTPUT
            echo "TENANT_ID=${{ secrets.PROD_TENANT_ID }}" >> $GITHUB_OUTPUT
          fi

      - name: Build and push Docker image
        run: |
          docker build -t ghcr.io/yourorg/atg:${{ steps.set-env.outputs.ENV }} .
          docker push ghcr.io/yourorg/atg:${{ steps.set-env.outputs.ENV }}

      - name: Deploy to Azure Container Instance
        run: |
          az deployment group create \
            --resource-group atg-infrastructure \
            --template-file infrastructure/container.bicep \
            --parameters \
              environment=${{ steps.set-env.outputs.ENV }} \
              targetTenantId=${{ steps.set-env.outputs.TENANT_ID }} \
              apiKeys=${{ secrets.ATG_API_KEYS }}
```

---

## 6. Security Specifications

### 6.1 Authentication & Authorization

**API Key Authentication**:
```python
# src/server/api/auth.py
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """Verify API key from Authorization header."""
    api_key = credentials.credentials

    # Load valid API keys from config
    config = ATGServerConfig.from_env()
    valid_keys = config.api_keys

    if api_key not in valid_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return api_key
```

**Azure Managed Identity**:
```python
# Target tenant authentication
from azure.identity import ManagedIdentityCredential, ClientSecretCredential

def get_azure_credential(config: ATGServerConfig):
    """Get Azure credential for target tenant access."""
    if config.use_managed_identity:
        return ManagedIdentityCredential()
    else:
        return ClientSecretCredential(
            tenant_id=config.target_tenant_id,
            client_id=config.service_principal_client_id,
            client_secret=config.service_principal_secret
        )
```

### 6.2 Network Security

- **HTTPS Only**: All API communication over TLS
- **API Key Rotation**: Support multiple keys for zero-downtime rotation
- **Rate Limiting**: Per-key rate limits (e.g., 100 requests/hour)
- **Network Isolation**: Container-to-container communication only within VNet

---

## 7. Error Handling & Resilience

### 7.1 Client-Side Error Handling

```python
class RemoteClient:
    async def submit_scan_job(self, tenant_id: str, config: Dict[str, Any]) -> str:
        """Submit scan job with retry logic."""
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = await self._http_client.post(
                    f"{self.service_url}/api/v1/scan",
                    json={"tenant_id": tenant_id, "config": config},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()["job_id"]

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                raise RemoteExecutionError(f"HTTP {e.response.status_code}: {e.response.text}")

            except httpx.TimeoutException:
                raise RemoteExecutionError(f"Request timeout after {self.timeout}s")

            except httpx.NetworkError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                raise RemoteExecutionError(f"Network error: {str(e)}")
```

### 7.2 Server-Side Error Handling

```python
class JobExecutor:
    async def execute_scan(self, job_id: str, tenant_id: str, config: Dict[str, Any]):
        """Execute scan with comprehensive error handling."""
        try:
            await self.queue.update_status(job_id, JobStatus.RUNNING)

            # Execute scan
            result = await self.grapher.build_graph(
                progress_callback=lambda stats: self._update_progress(job_id, stats)
            )

            await self.queue.store_result(job_id, result)
            await self.queue.update_status(job_id, JobStatus.COMPLETED)

        except AzureAuthenticationError as e:
            error_msg = f"Azure authentication failed: {str(e)}"
            logger.error(f"Job {job_id} failed: {error_msg}")
            await self.queue.update_status(
                job_id,
                JobStatus.FAILED,
                error=error_msg
            )

        except Neo4jConnectionError as e:
            error_msg = f"Database connection failed: {str(e)}"
            logger.error(f"Job {job_id} failed: {error_msg}")
            await self.queue.update_status(
                job_id,
                JobStatus.FAILED,
                error=error_msg
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(f"Job {job_id} failed with unexpected error")
            await self.queue.update_status(
                job_id,
                JobStatus.FAILED,
                error=error_msg
            )
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

**Client Tests**:
```python
# tests/client/test_remote_client.py
@pytest.mark.asyncio
async def test_submit_scan_job_success(mock_httpx_client):
    """Test successful scan job submission."""
    mock_httpx_client.post.return_value = httpx.Response(
        200,
        json={"job_id": "test-job-123"}
    )

    client = RemoteClient(
        service_url="https://test.example.com",
        api_key="test-key"  # pragma: allowlist secret
    )

    job_id = await client.submit_scan_job(
        tenant_id="tenant-123",
        config={}
    )

    assert job_id == "test-job-123"
    mock_httpx_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_submit_scan_job_auth_failure(mock_httpx_client):
    """Test authentication failure handling."""
    mock_httpx_client.post.return_value = httpx.Response(
        401,
        json={"detail": "Invalid API key"}
    )

    client = RemoteClient(
        service_url="https://test.example.com",
        api_key="invalid-key"  # pragma: allowlist secret
    )

    with pytest.raises(RemoteExecutionError, match="HTTP 401"):
        await client.submit_scan_job(tenant_id="tenant-123", config={})
```

**Server Tests**:
```python
# tests/server/test_api.py
@pytest.mark.asyncio
async def test_scan_endpoint_success(test_client, mock_job_queue):
    """Test scan endpoint with valid authentication."""
    response = await test_client.post(
        "/api/v1/scan",
        json={"tenant_id": "tenant-123", "config": {}},
        headers={"Authorization": "Bearer test-api-key"}
    )

    assert response.status_code == 200
    assert "job_id" in response.json()
    mock_job_queue.enqueue.assert_called_once()

@pytest.mark.asyncio
async def test_scan_endpoint_invalid_auth(test_client):
    """Test scan endpoint with invalid API key."""
    response = await test_client.post(
        "/api/v1/scan",
        json={"tenant_id": "tenant-123", "config": {}},
        headers={"Authorization": "Bearer invalid-key"}
    )

    assert response.status_code == 401
```

### 8.2 Integration Tests

```python
# tests/integration/test_end_to_end.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_scan_flow(
    running_atg_service,
    test_api_key,
    mock_azure_resources
):
    """Test complete scan flow from CLI to service."""
    # Initialize client
    client = RemoteClient(
        service_url=running_atg_service.url,
        api_key=test_api_key
    )

    # Submit job
    job_id = await client.submit_scan_job(
        tenant_id="test-tenant",
        config={"resource_limit": 10}
    )

    # Poll until complete
    while True:
        status = await client.get_job_status(job_id)
        if status.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(1)

    # Get result
    result = await client.get_job_result(job_id)

    assert result["success"] is True
    assert result["resources"] == 10
```

---

## 9. Monitoring & Observability

### 9.1 Metrics

**Key Metrics to Track**:
- Job queue depth
- Job execution duration (p50, p95, p99)
- API request rate and latency
- Error rate by endpoint
- Active worker count
- Neo4j query performance

**Implementation**:
```python
# src/server/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# API metrics
api_requests_total = Counter(
    "atg_api_requests_total",
    "Total API requests",
    ["endpoint", "method", "status"]
)

api_request_duration = Histogram(
    "atg_api_request_duration_seconds",
    "API request duration",
    ["endpoint", "method"]
)

# Job metrics
job_queue_depth = Gauge(
    "atg_job_queue_depth",
    "Number of jobs in queue"
)

job_execution_duration = Histogram(
    "atg_job_execution_duration_seconds",
    "Job execution duration",
    ["job_type"]
)

job_failures_total = Counter(
    "atg_job_failures_total",
    "Total job failures",
    ["job_type", "error_type"]
)
```

### 9.2 Logging

**Structured Logging**:
```python
import structlog

logger = structlog.get_logger()

# Example usage in job executor
logger.info(
    "scan_job_started",
    job_id=job_id,
    tenant_id=tenant_id,
    resource_limit=config.get("resource_limit")
)

logger.info(
    "scan_job_completed",
    job_id=job_id,
    duration_seconds=duration,
    resources_discovered=result["resources"]
)
```

---

## 10. Migration Strategy

### 10.1 Phase 1: Foundation (Week 1-2)

**Goal**: Implement core client-server infrastructure

**Tasks**:
1. Create `src/client/` module with `RemoteClient` and `ExecutionDispatcher`
2. Create `src/server/` module with FastAPI app skeleton
3. Implement API authentication with API keys
4. Add remote mode configuration to `config_manager.py`
5. Write unit tests for client and server modules

**Success Criteria**:
- Client can connect to server with authentication
- Server can accept and respond to basic requests
- Tests passing

### 10.2 Phase 2: Job Queue (Week 2-3)

**Goal**: Implement async job processing

**Tasks**:
1. Set up Redis container in development environment
2. Implement `JobQueue` class with Redis backend
3. Create `JobExecutor` that wraps existing ATG services
4. Implement job status polling endpoints
5. Add integration tests for job flow

**Success Criteria**:
- Jobs can be enqueued and executed asynchronously
- Job status can be polled
- Multiple jobs can run concurrently

### 10.3 Phase 3: CLI Integration (Week 3-4)

**Goal**: Integrate remote mode into CLI

**Tasks**:
1. Modify CLI commands to support `--remote` flag
2. Implement `ExecutionDispatcher` routing logic
3. Add progress display for remote job polling
4. Test all CLI commands in remote mode
5. Update CLI documentation

**Success Criteria**:
- All CLI commands work in both local and remote modes
- User experience is consistent between modes
- Progress display works for remote jobs

### 10.4 Phase 4: Deployment (Week 4-5)

**Goal**: Deploy to Azure Container Instances

**Tasks**:
1. Create Dockerfile for service
2. Write Azure Container Instance Terraform/Bicep templates
3. Set up GitHub Actions deployment workflows
4. Configure three environments (dev/int/prod)
5. Test end-to-end deployment

**Success Criteria**:
- Service deployed to all three environments
- GitHub Actions automatically deploys on branch push
- Each environment targets correct tenant
- Monitoring and logging operational

### 10.5 Phase 5: Documentation & Rollout (Week 5-6)

**Goal**: Document and enable user adoption

**Tasks**:
1. Write user documentation for remote mode
2. Create environment setup guide
3. Document API for potential future integrations
4. Train team on remote mode usage
5. Monitor initial production usage

**Success Criteria**:
- Complete documentation available
- Users can set up and use remote mode
- No critical issues in production

---

## 11. Risk Mitigation

### 11.1 Identified Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Breaking existing CLI behavior** | High | Medium | Extensive backward compatibility testing, remote mode opt-in only |
| **Service downtime affects users** | High | Low | Multiple environments, health checks, auto-restart |
| **Azure API rate limiting** | Medium | Medium | Implement job queue with concurrency limits |
| **Large artifact downloads fail** | Medium | Medium | Chunk downloads, resume capability, artifact expiration |
| **Authentication compromise** | High | Low | API key rotation, separate keys per environment, audit logging |
| **Neo4j database corruption** | High | Low | Regular backups, separate DB per environment |
| **Job queue overflow** | Medium | Low | Queue depth monitoring, job timeout enforcement |

### 11.2 Rollback Plan

If critical issues arise:

1. **Immediate**: Set `ATG_REMOTE_MODE=false` in user environments (falls back to local mode)
2. **Short-term**: Disable remote mode in CLI defaults
3. **Long-term**: If fundamental issues, remove remote mode code (modules are isolated)

---

## 12. Success Metrics

### 12.1 Technical Metrics

- **Backward Compatibility**: 100% of existing CLI commands work without changes
- **Remote Mode Adoption**: 50% of users using remote mode within 3 months
- **Service Availability**: 99.5% uptime across all environments
- **Job Success Rate**: >95% of submitted jobs complete successfully
- **API Latency**: p95 response time <200ms for status endpoints

### 12.2 User Experience Metrics

- **Remote Scan Duration**: Comparable to local mode (within 20%)
- **Error Rate**: <5% of remote operations fail
- **Documentation Clarity**: <10% of users need support for setup

---

## 13. Appendices

### Appendix A: API Reference

Complete OpenAPI schema will be auto-generated by FastAPI at `/docs` endpoint.

### Appendix B: Environment Variables Reference

**Client-Side**:
```bash
# Enable remote mode
ATG_REMOTE_MODE=true

# Service connection
ATG_SERVICE_URL=https://atg-service-dev.azurecontainer.io
ATG_API_KEY=your-api-key-here

# Timeouts
ATG_REQUEST_TIMEOUT=300
ATG_JOB_POLL_INTERVAL=5
```

**Server-Side**:
```bash
# Server configuration
ATG_SERVER_HOST=0.0.0.0
ATG_SERVER_PORT=8000
ATG_SERVER_WORKERS=4

# Authentication
ATG_API_KEYS=key1,key2,key3

# Job queue
REDIS_URL=redis://localhost:6379
ATG_MAX_CONCURRENT_JOBS=3

# Target tenant
ATG_TARGET_TENANT_ID=your-target-tenant-id
ATG_TARGET_SUBSCRIPTION_ID=your-target-subscription-id

# Azure authentication
ATG_USE_MANAGED_IDENTITY=true
AZURE_CLIENT_ID=optional-service-principal-id
AZURE_CLIENT_SECRET=optional-service-principal-secret

# Neo4j (reuse existing vars)
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=your-neo4j-password
```

### Appendix C: Module Dependency Graph

```
CLI (scripts/cli.py)
  ↓
ExecutionDispatcher (src/client/execution_dispatcher.py)
  ↓
  ├──► Local Mode: Existing ATG services (unchanged)
  │
  └──► Remote Mode: RemoteClient (src/client/remote_client.py)
         ↓
         ATG Service (src/server/main.py)
           ↓
           JobQueue (src/server/jobs/queue.py)
             ↓
             JobExecutor (src/server/jobs/executor.py)
               ↓
               Existing ATG Services (unchanged):
                 • AzureTenantGrapher
                 • AzureDiscoveryService
                 • ResourceProcessingService
                 • IaC Emitters
```

---

## 14. Conclusion

This architecture enables ATG to operate as a client-server system while maintaining 100% backward compatibility with existing local CLI usage. The design follows the brick philosophy with clear module boundaries, enabling each component to be independently developed, tested, and regenerated.

**Key Strengths**:
- ✅ Backward compatible (local mode unchanged)
- ✅ Modular design (client, server, queue are separate bricks)
- ✅ Zero changes to existing ATG core services
- ✅ Async job queue for long-running operations
- ✅ Multi-environment deployment support
- ✅ Comprehensive error handling and monitoring
- ✅ Clear migration path with 5 phases

**Next Steps**: Proceed with Phase 1 implementation (Foundation) following the module specifications in Section 2.
