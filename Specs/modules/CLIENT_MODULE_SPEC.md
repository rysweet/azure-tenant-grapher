# Module: ATG Client (Remote Mode)

## Purpose

Enable CLI to communicate with remote ATG service for distributed execution of Azure tenant scanning and IaC generation operations.

## Module Location

```
src/client/
├── __init__.py              # Public API exports
├── remote_client.py         # REST API client implementation
├── execution_dispatcher.py  # Local vs remote mode routing
├── config.py                # Client configuration
├── exceptions.py            # Client-specific exceptions
└── tests/
    ├── __init__.py
    ├── test_remote_client.py
    ├── test_dispatcher.py
    ├── test_config.py
    └── fixtures/
        └── mock_responses.py
```

## Public API (Studs)

### RemoteClient

```python
class RemoteClient:
    """
    REST API client for communicating with remote ATG service.

    Handles authentication, request retries, and artifact downloads.
    """

    def __init__(
        self,
        service_url: str,
        api_key: str,
        timeout: int = 300,
        max_retries: int = 3
    ):
        """
        Initialize remote client.

        Args:
            service_url: Base URL of ATG service (e.g., https://atg.example.com)
            api_key: Authentication API key
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """

    async def submit_scan_job(
        self,
        tenant_id: str,
        config: Dict[str, Any]
    ) -> str:
        """
        Submit async scan job to remote service.

        Args:
            tenant_id: Azure tenant ID to scan
            config: Scan configuration (filters, limits, etc.)

        Returns:
            Job ID for status polling

        Raises:
            RemoteExecutionError: If submission fails
            AuthenticationError: If API key is invalid
        """

    async def get_job_status(self, job_id: str) -> JobStatusResponse:
        """
        Get current status of a job.

        Args:
            job_id: Job identifier

        Returns:
            JobStatusResponse with status, progress, and error info

        Raises:
            RemoteExecutionError: If status check fails
            JobNotFoundError: If job ID doesn't exist
        """

    async def get_job_result(self, job_id: str) -> Dict[str, Any]:
        """
        Retrieve completed job results.

        Args:
            job_id: Job identifier

        Returns:
            Dictionary with job results (resources discovered, etc.)

        Raises:
            RemoteExecutionError: If retrieval fails
            JobNotCompleteError: If job is not in COMPLETED state
        """

    async def download_artifacts(
        self,
        job_id: str,
        output_dir: Path
    ) -> List[Path]:
        """
        Download generated artifacts (IaC files).

        Args:
            job_id: Job identifier
            output_dir: Local directory to save files

        Returns:
            List of downloaded file paths

        Raises:
            RemoteExecutionError: If download fails
            ArtifactsNotAvailableError: If artifacts don't exist
        """

    async def cancel_job(self, job_id: str) -> None:
        """
        Cancel a running job.

        Args:
            job_id: Job identifier

        Raises:
            RemoteExecutionError: If cancellation fails
        """

    async def health_check(self) -> bool:
        """
        Check if service is healthy and reachable.

        Returns:
            True if service is healthy, False otherwise
        """
```

### ExecutionDispatcher

```python
class ExecutionDispatcher:
    """
    Routes CLI commands to local or remote execution based on configuration.
    """

    def __init__(self, config: ATGClientConfig):
        """
        Initialize dispatcher with client configuration.

        Args:
            config: Client configuration with remote mode settings
        """

    async def execute_scan(
        self,
        tenant_id: str,
        **kwargs
    ) -> ScanResult:
        """
        Execute scan in appropriate mode (local or remote).

        Args:
            tenant_id: Azure tenant ID
            **kwargs: Additional scan parameters

        Returns:
            ScanResult with discovered resources and statistics

        Raises:
            ExecutionError: If scan fails in either mode
        """

    async def execute_iac_generation(
        self,
        tenant_id: str,
        output_format: str,
        output_dir: Path,
        **kwargs
    ) -> IaCGenerationResult:
        """
        Execute IaC generation in appropriate mode.

        Args:
            tenant_id: Azure tenant ID
            output_format: terraform, bicep, or arm
            output_dir: Directory to save generated files
            **kwargs: Additional generation parameters

        Returns:
            IaCGenerationResult with generated file paths

        Raises:
            ExecutionError: If generation fails
        """

    async def execute_tenant_creation(
        self,
        spec_file: Path,
        **kwargs
    ) -> TenantCreationResult:
        """
        Execute tenant creation in appropriate mode.

        Args:
            spec_file: Path to tenant specification markdown
            **kwargs: Additional creation parameters

        Returns:
            TenantCreationResult with deployment status

        Raises:
            ExecutionError: If creation fails
        """

    def is_remote_mode(self) -> bool:
        """Check if remote mode is configured and enabled."""

    async def _execute_local(self, operation: str, **kwargs) -> Any:
        """Execute operation using local ATG services."""

    async def _execute_remote(self, operation: str, **kwargs) -> Any:
        """Execute operation via remote service."""
```

### Configuration

```python
@dataclass
class ATGClientConfig:
    """Client-side configuration for ATG operations."""

    # Mode selection
    remote_mode: bool = False

    # Remote service connection
    service_url: Optional[str] = None
    api_key: Optional[str] = None

    # Timeout settings
    request_timeout: int = 300
    job_poll_interval: int = 5
    job_max_wait: int = 3600

    # Retry settings
    max_retries: int = 3
    retry_backoff_factor: float = 2.0

    # Progress display
    show_progress: bool = True
    progress_update_interval: int = 2

    @classmethod
    def from_env(cls) -> "ATGClientConfig":
        """Load configuration from environment variables."""

    def validate(self) -> None:
        """Validate configuration is complete and correct."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
```

### Response Models

```python
@dataclass
class JobStatusResponse:
    """Job status information."""
    job_id: str
    status: JobStatus
    progress: Optional[float]  # 0.0 to 1.0
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str]

@dataclass
class ScanResult:
    """Scan operation result."""
    success: bool
    subscriptions: int
    resources: int
    duration_seconds: float
    error: Optional[str]

@dataclass
class IaCGenerationResult:
    """IaC generation result."""
    success: bool
    output_format: str
    files_generated: List[Path]
    resources_included: int
    duration_seconds: float
    error: Optional[str]

@dataclass
class TenantCreationResult:
    """Tenant creation result."""
    success: bool
    resources_created: int
    resources_failed: int
    deployment_logs: List[str]
    duration_seconds: float
    error: Optional[str]
```

### Exceptions

```python
class RemoteExecutionError(Exception):
    """Base exception for remote execution failures."""

class AuthenticationError(RemoteExecutionError):
    """API key authentication failed."""

class JobNotFoundError(RemoteExecutionError):
    """Job ID does not exist."""

class JobNotCompleteError(RemoteExecutionError):
    """Job is not in COMPLETED state."""

class ArtifactsNotAvailableError(RemoteExecutionError):
    """Job artifacts not available for download."""

class ServiceUnavailableError(RemoteExecutionError):
    """Remote service is not reachable."""

class ExecutionError(Exception):
    """Base exception for execution failures (local or remote)."""
```

## Contract

### Inputs
- **Configuration**: Service URL, API key, timeout settings
- **Command Parameters**: Tenant IDs, filter config, output directories
- **User Preferences**: Progress display, polling interval

### Outputs
- **Job Status**: Real-time status updates, progress percentage
- **Results**: Scan statistics, generated file paths
- **Errors**: Detailed error messages with remediation guidance

### Side Effects
- **Network Requests**: HTTPS calls to remote service
- **File Downloads**: Artifacts saved to local filesystem
- **Progress Display**: Console output during polling

### Dependencies
- **External Libraries**:
  - `httpx`: Async HTTP client
  - `pydantic`: Data validation
  - `typer`: CLI framework integration
  - `rich`: Progress display

- **Internal Dependencies**:
  - `src.config_manager`: Configuration management
  - `src.exceptions`: Base exception classes
  - Existing CLI commands (for local mode fallback)

## Implementation Notes

### HTTP Client Configuration

```python
# Use httpx with connection pooling
import httpx

class RemoteClient:
    def __init__(self, ...):
        self._http_client = httpx.AsyncClient(
            base_url=service_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5
            ),
            headers={
                "User-Agent": "ATG-CLI/1.0",
                "Authorization": f"Bearer {api_key}"
            }
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._http_client.aclose()
```

### Retry Logic

```python
# Exponential backoff for transient failures
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

class RemoteClient:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException))
    )
    async def submit_scan_job(self, ...):
        # Will automatically retry on network/timeout errors
        pass
```

### Progress Polling

```python
# User-friendly progress display
from rich.progress import Progress, SpinnerColumn, TextColumn

async def wait_for_job_completion(
    client: RemoteClient,
    job_id: str
) -> JobStatusResponse:
    """Poll job status with progress display."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("Executing remote scan...", total=None)

        while True:
            status = await client.get_job_status(job_id)

            if status.status == JobStatus.COMPLETED:
                progress.update(task, description="✅ Scan completed")
                return status

            elif status.status == JobStatus.FAILED:
                progress.update(task, description="❌ Scan failed")
                raise RemoteExecutionError(status.error)

            # Update progress if available
            if status.progress is not None:
                progress.update(
                    task,
                    description=f"Scanning... {status.progress * 100:.0f}%"
                )

            await asyncio.sleep(5)
```

### Artifact Download with Progress

```python
# Download large files with progress bar
async def download_artifacts(
    self,
    job_id: str,
    output_dir: Path
) -> List[Path]:
    """Download artifacts with progress tracking."""

    response = await self._http_client.get(
        f"/api/v1/jobs/{job_id}/artifacts",
        stream=True
    )

    downloaded_files = []
    total_size = int(response.headers.get("Content-Length", 0))

    with Progress() as progress:
        task = progress.add_task("Downloading artifacts...", total=total_size)

        output_file = output_dir / f"artifacts-{job_id}.zip"
        with open(output_file, "wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=8192):
                f.write(chunk)
                progress.update(task, advance=len(chunk))

    # Extract zip
    import zipfile
    with zipfile.ZipFile(output_file, "r") as zip_ref:
        zip_ref.extractall(output_dir)
        downloaded_files = [output_dir / name for name in zip_ref.namelist()]

    output_file.unlink()  # Remove zip after extraction
    return downloaded_files
```

## Test Requirements

### Unit Tests

1. **test_remote_client.py**:
   - Test successful job submission
   - Test authentication failures
   - Test network error handling
   - Test timeout handling
   - Test retry logic
   - Test artifact downloads

2. **test_dispatcher.py**:
   - Test local mode routing
   - Test remote mode routing
   - Test mode detection from config
   - Test fallback scenarios

3. **test_config.py**:
   - Test configuration loading from env
   - Test validation logic
   - Test default values

### Integration Tests

```python
# tests/integration/test_client_server.py
@pytest.mark.integration
async def test_full_scan_workflow(running_service, test_api_key):
    """Test complete scan workflow from client to service."""

    config = ATGClientConfig(
        remote_mode=True,
        service_url=running_service.url,
        api_key=test_api_key
    )

    dispatcher = ExecutionDispatcher(config)

    # Execute scan
    result = await dispatcher.execute_scan(
        tenant_id="test-tenant-123"
    )

    # Verify results
    assert result.success is True
    assert result.resources > 0
```

## Backward Compatibility

- Remote mode is **opt-in** via `--remote` flag or `ATG_REMOTE_MODE=true`
- Default behavior (local mode) unchanged
- All existing CLI commands work without modification
- Configuration validation prevents accidental remote mode activation

## Performance Considerations

- **Connection Pooling**: Reuse HTTP connections for multiple requests
- **Parallel Downloads**: Download multiple artifact files concurrently
- **Efficient Polling**: Use exponential backoff to reduce API load
- **Progress Caching**: Cache status responses to avoid redundant queries

## Security Considerations

- **API Key Storage**: Never log or print API keys
- **HTTPS Only**: Enforce TLS for all communications
- **Credential Validation**: Validate credentials before first use
- **Error Messages**: Sanitize error messages to prevent credential leakage

## Future Enhancements

- **WebSocket Support**: Real-time job updates instead of polling
- **Batch Operations**: Submit multiple jobs in one request
- **Caching**: Cache service capabilities and reduce network calls
- **Offline Mode**: Queue operations when service is unreachable
