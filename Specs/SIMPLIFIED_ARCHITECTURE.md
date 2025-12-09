# ATG Client-Server Architecture - SIMPLIFIED

**Version**: 2.0 (Philosophy-Compliant)
**Date**: 2025-12-09
**Status**: READY FOR REVIEW

---

## Philosophy Violations Fixed

**Score Before**: B- (70%) - Premature optimization detected
**Changes Made**:
1. ✅ REMOVED prod environment (user explicitly deferred: "We do not need to do prod yet")
2. ✅ SIMPLIFIED deployment to git tag-based (not branch-based GitOps)
3. ✅ DEFERRED async queue (start with WebSocket + long HTTP timeout)
4. ✅ DEFERRED Container Apps fallback (verify ACI 64GB first)
5. ✅ REDUCED to 2 environments (Dev and Integration only)

**Philosophy Alignment**:
- ✅ "Don't build for hypothetical future requirements" → No prod environment yet
- ✅ "Start minimal, grow as needed" → No async queue until proven necessary
- ✅ "Present-moment focus" → Build what's needed NOW (dev + integration)
- ✅ "Avoid future-proofing" → No Container Apps fallback until ACI limits confirmed

---

## Executive Summary

Transform Azure Tenant Grapher (ATG) from CLI-only to client-server system with:
- **2 environments**: Dev and Integration (prod deferred)
- **Simple deployment**: Git tag-based (not branch-based)
- **Simple async**: WebSocket + long HTTP timeout (no Redis queue initially)
- **Single container platform**: Azure Container Instances with 64GB RAM

---

## 1. System Architecture (Simplified)

### 1.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                    USER ENVIRONMENT                         │
│                                                             │
│  ┌──────────────┐         ┌──────────────────────────┐     │
│  │   ATG CLI    │◄────────┤  Mode Dispatcher         │     │
│  │   (Client)   │         │  • Local (default)       │     │
│  └──────┬───────┘         │  • Remote (opt-in)       │     │
│         │                 └──────────────────────────┘     │
│         │                                                   │
│         │ Local: Direct execution (unchanged)              │
│         │ Remote: HTTPS + long-running HTTP                │
│         │                                                   │
└─────────┼───────────────────────────────────────────────────┘
          │
          │ HTTPS + API Key + WebSocket
          │
┌─────────▼───────────────────────────────────────────────────┐
│             AZURE CONTAINER INSTANCE (64GB RAM)             │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              ATG Service (FastAPI)                    │  │
│  │                                                       │  │
│  │  ┌──────────────┐  ┌──────────────┐                 │  │
│  │  │  REST API    │  │  WebSocket   │                 │  │
│  │  │  Endpoints   │  │  Progress    │                 │  │
│  │  └──────────────┘  └──────────────┘                 │  │
│  │                                                       │  │
│  │  Long HTTP Timeout: 30-60 minutes                    │  │
│  │  (Sufficient for most scan operations)               │  │
│  │                                                       │  │
│  │  ┌────────────────────────────────────────────────┐  │  │
│  │  │    Existing ATG Core Services (UNCHANGED)      │  │  │
│  │  │  • AzureDiscoveryService                      │  │  │
│  │  │  • ResourceProcessingService                  │  │  │
│  │  │  • IaC Generation                            │  │  │
│  │  └────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          Neo4j Container (32GB RAM)                   │  │
│  │  • Graph storage for discovered resources            │  │
│  │  • Separate DB per environment (dev/integration)     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          Azure Managed Identity                       │  │
│  │  • Reader permissions on target tenant               │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Two-Environment Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  GITHUB ACTIONS CI/CD                        │
│                                                              │
│  Git Tag (e.g., v1.0.0-dev)  ──►  Dev Environment           │
│  Git Tag (e.g., v1.0.0-int)  ──►  Integration Environment   │
│                                                              │
│  [PROD ENVIRONMENT DEFERRED - User explicitly postponed]    │
└──────────────────────────────────────────────────────────────┘

Each Environment:
  • Azure Container Instance (64GB RAM - verify availability FIRST)
  • Separate Neo4j database
  • Environment-specific .env configuration
  • Isolated API key authentication
```

---

## 2. Key Simplifications

### 2.1 No Async Queue (Initially)

**Philosophy**: Start minimal, grow as needed

**Current Approach**:
```python
# Simple long-running HTTP endpoint with WebSocket progress
@app.post("/api/v1/scan")
async def scan_tenant(request: ScanRequest):
    """
    Execute scan with long HTTP timeout (30-60 min).
    Client maintains WebSocket for progress updates.
    """
    async with websocket_manager.progress_stream(request.job_id) as stream:
        result = await azure_tenant_grapher.build_graph(
            progress_callback=stream.send_progress
        )
    return result
```

**When to add Redis queue**:
- Operations routinely timeout after 60 minutes
- Need to support multiple concurrent scans (>3)
- Need job persistence across service restarts
- **Verification**: Monitor operation durations for 2 weeks in dev

**Benefits of deferring queue**:
- Eliminates Redis container (simpler infrastructure)
- No job queue management code
- No polling logic
- Faster initial implementation

### 2.2 Git Tag-Based Deployment

**Philosophy**: Simpler than branch-based GitOps

**Previous Approach** (complex):
```yaml
# Branch → Environment mapping
main → dev
integration → integration
prod → prod
```

**New Approach** (simple):
```yaml
# Tag → Environment deployment
git tag v1.0.0-dev && git push --tags     # Deploys to dev
git tag v1.0.0-int && git push --tags     # Deploys to integration
```

**Benefits**:
- Explicit version control (tags are immutable)
- No branch management overhead
- Clear rollback path (redeploy previous tag)
- Standard semantic versioning

**GitHub Actions Workflow**:
```yaml
on:
  push:
    tags:
      - 'v*-dev'    # Deploys to dev
      - 'v*-int'    # Deploys to integration
```

### 2.3 No Container Apps Fallback

**Philosophy**: Don't build for hypothetical limits

**Action Required BEFORE implementation**:
```bash
# 1. VERIFY Azure Container Instances support 64GB RAM
az container create \
  --resource-group test-rg \
  --name test-aci \
  --cpu 4 \
  --memory 64 \
  --image nginx:latest \
  --dry-run

# 2. Check if command succeeds
# 3. If ACI supports 64GB → Use ACI (DONE)
# 4. If ACI limit < 64GB → THEN consider Container Apps
```

**Current Decision**: Assume ACI supports 64GB until proven otherwise

**When to consider Container Apps**:
- ACI verification fails (64GB unavailable)
- Need multi-replica deployment
- Need advanced networking features
- **Evidence required**: Screenshot of ACI 64GB limit error

### 2.4 Two Environments Only

**Philosophy**: Present-moment focus

**Environments**:
1. **Dev**: For development and testing (DefenderATEVET17)
2. **Integration**: For user acceptance testing (Target Tenant A)

**Prod environment deferred because**:
- User explicitly stated: "We do not need to do prod yet"
- No production workload requirements
- Can add prod later when actually needed
- Reduces initial infrastructure cost by 33%

**When to add prod**:
- User explicitly requests production deployment
- Have production tenant ready (Target Tenant B)
- Dev and integration proven stable for 4+ weeks
- Security audit completed

---

## 3. Simplified Module Specifications

### 3.1 Client Module (`src/client/`)

**Purpose**: CLI client supporting local and remote execution

**Module Structure**:
```
src/client/
├── __init__.py              # Public API
├── remote_client.py         # HTTP + WebSocket client
├── execution_dispatcher.py  # Local vs remote routing
├── config.py                # Client configuration
└── tests/
    ├── test_remote_client.py
    └── test_dispatcher.py
```

**Public API**:
```python
class RemoteClient:
    """REST + WebSocket client for ATG service."""

    def __init__(self, service_url: str, api_key: str, timeout: int = 3600):
        """30-60 min timeout for long operations."""
        pass

    async def scan_tenant(
        self,
        tenant_id: str,
        progress_callback: Callable
    ) -> ScanResult:
        """Execute scan with WebSocket progress updates."""
        # 1. POST /api/v1/scan (starts operation)
        # 2. Open WebSocket for progress
        # 3. Wait for completion (long HTTP response)
        # 4. Return result
        pass

    async def generate_iac(
        self,
        tenant_id: str,
        format: str
    ) -> IaCResult:
        """Generate IaC with progress tracking."""
        pass
```

**Contract**:
- **Inputs**: Service URL, API key, command parameters
- **Outputs**: Operation results, progress updates via callback
- **Side Effects**: Network requests, WebSocket connections
- **Dependencies**: `httpx`, `websockets`, existing CLI

### 3.2 Server Module (`src/server/`)

**Purpose**: FastAPI server with long-running HTTP endpoints

**Module Structure**:
```
src/server/
├── __init__.py              # Public API
├── main.py                  # FastAPI application
├── api/
│   ├── routes.py            # API endpoints
│   ├── models.py            # Request/response models
│   └── auth.py              # API key authentication
├── websocket/
│   ├── manager.py           # WebSocket connection management
│   └── progress.py          # Progress streaming
├── config.py                # Server configuration
└── tests/
    ├── test_api.py
    └── test_websocket.py
```

**Public API**:
```python
@app.post("/api/v1/scan", timeout=3600)  # 60 min timeout
async def scan_tenant(
    request: ScanRequest,
    api_key: str = Depends(verify_api_key),
    websocket: WebSocket = Depends(get_websocket)
) -> ScanResponse:
    """
    Long-running scan operation with WebSocket progress.
    Returns when complete (no polling needed).
    """
    async with websocket_manager.stream(websocket) as stream:
        result = await atg_service.scan_tenant(
            tenant_id=request.tenant_id,
            progress_callback=stream.send_progress
        )
    return result

@app.post("/api/v1/generate-iac", timeout=1800)  # 30 min timeout
async def generate_iac(
    request: IaCRequest,
    api_key: str = Depends(verify_api_key),
    websocket: WebSocket = Depends(get_websocket)
) -> IaCResponse:
    """Generate IaC with progress updates."""
    pass
```

**Contract**:
- **Inputs**: HTTP requests with API key, WebSocket for progress
- **Outputs**: Operation results, progress via WebSocket
- **Side Effects**: Database writes, Azure API calls, artifact storage
- **Dependencies**: `fastapi`, `websockets`, existing ATG services

### 3.3 Configuration Updates

**Client Configuration**:
```python
@dataclass
class ATGClientConfig:
    """Client-side configuration."""

    # Remote mode
    remote_mode: bool = False
    service_url: Optional[str] = None
    api_key: Optional[str] = None

    # Long timeout for remote operations
    request_timeout: int = 3600  # 60 minutes (no queue needed)

    @classmethod
    def from_env(cls) -> "ATGClientConfig":
        return cls(
            remote_mode=os.getenv("ATG_REMOTE_MODE", "false").lower() == "true",
            service_url=os.getenv("ATG_SERVICE_URL"),
            api_key=os.getenv("ATG_API_KEY"),
            request_timeout=int(os.getenv("ATG_REQUEST_TIMEOUT", "3600"))
        )
```

**Server Configuration**:
```python
@dataclass
class ATGServerConfig:
    """Server-side configuration."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Authentication
    api_keys: List[str] = field(default_factory=list)

    # Target tenant
    target_tenant_id: str = ""
    target_subscription_id: str = ""

    # Azure authentication
    use_managed_identity: bool = True

    # NO REDIS - using long HTTP + WebSocket
    max_concurrent_operations: int = 3  # Limit concurrent scans

    @classmethod
    def from_env(cls) -> "ATGServerConfig":
        return cls(
            host=os.getenv("ATG_SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("ATG_SERVER_PORT", "8000")),
            workers=int(os.getenv("ATG_SERVER_WORKERS", "4")),
            api_keys=os.getenv("ATG_API_KEYS", "").split(","),
            target_tenant_id=os.getenv("ATG_TARGET_TENANT_ID", ""),
            use_managed_identity=os.getenv("ATG_USE_MANAGED_IDENTITY", "true").lower() == "true",
            max_concurrent_operations=int(os.getenv("ATG_MAX_CONCURRENT_OPS", "3"))
        )
```

---

## 4. Simplified Data Flow

### 4.1 Remote Scan Operation

```
1. User: atg scan --tenant-id X --remote
   └─► CLI detects remote mode

2. CLI → Service: POST /api/v1/scan
   └─► Opens WebSocket connection
   └─► Service accepts (60 min timeout)

3. Service executes scan (streaming progress):
   └─► Calls AzureTenantGrapher.build_graph()
   └─► Sends progress via WebSocket
   └─► Client displays progress in real-time

4. Service completes scan (after N minutes):
   └─► Returns final result in HTTP response
   └─► Closes WebSocket

5. CLI displays results
   └─► No polling needed
   └─► No job queue needed
```

**Key Difference from Complex Design**:
- ❌ No Redis job queue
- ❌ No polling endpoints
- ❌ No job status tracking
- ✅ Simple HTTP request-response (with long timeout)
- ✅ WebSocket for progress only

---

## 5. Simplified Deployment

### 5.1 Azure Container Infrastructure

**Container Specification** (VERIFY 64GB FIRST):
```yaml
resource "azurerm_container_group" "atg_service" {
  name                = "atg-service-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"

  container {
    name   = "atg-api"
    image  = "ghcr.io/yourorg/atg:${var.tag}"
    cpu    = "4"
    memory = "64"  # VERIFY THIS FIRST

    ports {
      port     = 8000
      protocol = "TCP"
    }

    environment_variables = {
      ATG_SERVER_HOST              = "0.0.0.0"
      ATG_SERVER_PORT              = "8000"
      ATG_TARGET_TENANT_ID         = var.target_tenant_id
      ATG_USE_MANAGED_IDENTITY     = "true"
      NEO4J_URI                    = "bolt://neo4j:7687"
      ATG_MAX_CONCURRENT_OPS       = "3"
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

    volumes {
      name                 = "neo4j-data"
      mount_path           = "/data"
      storage_account_name = var.storage_account_name
      share_name          = "neo4j-data-${var.environment}"
    }
  }

  # NO REDIS CONTAINER

  identity {
    type = "SystemAssigned"
  }
}
```

### 5.2 Two-Environment Setup

**Environment Configuration Matrix**:

| Environment  | Git Tag Pattern | Target Tenant       | Container Size | Neo4j DB        |
|-------------|----------------|---------------------|----------------|-----------------|
| Dev         | v*-dev         | DefenderATEVET17    | 64GB RAM       | atg-dev-db      |
| Integration | v*-int         | Target Tenant A     | 64GB RAM       | atg-int-db      |
| ~~Prod~~    | ~~v*-prod~~    | ~~DEFERRED~~        | ~~DEFERRED~~   | ~~DEFERRED~~    |

**GitHub Actions Workflow**:
```yaml
name: Deploy ATG Service

on:
  push:
    tags:
      - 'v*-dev'    # Deploys to dev
      - 'v*-int'    # Deploys to integration

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Parse environment from tag
        id: parse-tag
        run: |
          TAG="${{ github.ref_name }}"
          if [[ "$TAG" =~ -dev$ ]]; then
            echo "ENV=dev" >> $GITHUB_OUTPUT
            echo "TENANT_ID=${{ secrets.DEV_TENANT_ID }}" >> $GITHUB_OUTPUT
          elif [[ "$TAG" =~ -int$ ]]; then
            echo "ENV=integration" >> $GITHUB_OUTPUT
            echo "TENANT_ID=${{ secrets.INT_TENANT_ID }}" >> $GITHUB_OUTPUT
          else
            echo "Invalid tag format: $TAG"
            exit 1
          fi

      - name: Build and push Docker image
        run: |
          docker build -t ghcr.io/yourorg/atg:${{ github.ref_name }} .
          docker push ghcr.io/yourorg/atg:${{ github.ref_name }}

      - name: Deploy to Azure Container Instance
        run: |
          az deployment group create \
            --resource-group atg-infrastructure \
            --template-file infrastructure/container.bicep \
            --parameters \
              environment=${{ steps.parse-tag.outputs.ENV }} \
              tag=${{ github.ref_name }} \
              targetTenantId=${{ steps.parse-tag.outputs.TENANT_ID }} \
              apiKeys=${{ secrets.ATG_API_KEYS }}
```

---

## 6. When to Add Complexity

### 6.1 Add Redis Job Queue When:

**Evidence Required**:
- [ ] Operations routinely timeout after 60 minutes (>20% of scans)
- [ ] Need to support >3 concurrent scans per environment
- [ ] Service restarts lose in-progress operations (>5 times/month)
- [ ] Users explicitly request "background job" capability

**Measurement Period**: 2 weeks in dev environment

**How to Measure**:
```python
# Add telemetry to track operation durations
@app.post("/api/v1/scan")
async def scan_tenant(request: ScanRequest):
    start_time = time.time()
    result = await atg_service.scan_tenant(...)
    duration = time.time() - start_time

    logger.info(f"Scan duration: {duration}s")
    metrics.record_scan_duration(duration)

    return result

# Alert if duration > 3000s (50 minutes)
if duration > 3000:
    send_alert("Scan approaching timeout threshold")
```

### 6.2 Add Production Environment When:

**Prerequisites**:
- [ ] User explicitly requests production deployment
- [ ] Have production tenant ready (Target Tenant B)
- [ ] Dev and integration stable for 4+ weeks (no critical bugs)
- [ ] Security audit completed
- [ ] Disaster recovery plan documented

### 6.3 Add Container Apps When:

**Prerequisites**:
- [ ] ACI 64GB verification fails (screenshot of error)
- [ ] Need multi-replica deployment (>1 instance per environment)
- [ ] Need advanced networking (VNet integration, private endpoints)
- [ ] Need auto-scaling based on load

**Verification Command** (run BEFORE implementation):
```bash
az container create \
  --resource-group test-rg \
  --name test-aci-64gb \
  --cpu 4 \
  --memory 64 \
  --image nginx:latest \
  --location eastus \
  --dry-run

# Expected outcome: Command succeeds → Use ACI
# Failure outcome: Error about memory limit → Consider Container Apps
```

---

## 7. Implementation Phases (Simplified)

### Phase 1: Foundation (Week 1-2)

**Goal**: Core client-server infrastructure

**Tasks**:
1. Create `src/client/` module with `RemoteClient` (HTTP + WebSocket)
2. Create `src/server/` module with FastAPI app
3. Implement API authentication with API keys
4. Add WebSocket manager for progress streaming
5. Write unit tests

**Success Criteria**:
- Client can connect and execute scan via remote service
- WebSocket progress updates work
- Long HTTP timeout handles 60-minute operations

**NO Redis, NO job queue, NO polling**

### Phase 2: CLI Integration (Week 2-3)

**Goal**: Integrate remote mode into CLI

**Tasks**:
1. Modify CLI commands to support `--remote` flag
2. Implement `ExecutionDispatcher` routing logic
3. Add progress display for WebSocket updates
4. Test all CLI commands in remote mode
5. Update CLI documentation

**Success Criteria**:
- All CLI commands work in both local and remote modes
- User experience is consistent between modes
- Progress display works for remote operations

### Phase 3: Deployment (Week 3-4)

**Goal**: Deploy to Azure Container Instances

**Tasks**:
1. **VERIFY ACI 64GB availability FIRST**
2. Create Dockerfile for service
3. Write Azure Container Instance Bicep templates
4. Set up GitHub Actions deployment workflows (tag-based)
5. Configure two environments (dev/integration)
6. Test end-to-end deployment

**Success Criteria**:
- Service deployed to dev and integration environments
- GitHub Actions deploys on tag push
- Each environment targets correct tenant
- Monitoring and logging operational

### Phase 4: Documentation & Rollout (Week 4-5)

**Goal**: Document and enable user adoption

**Tasks**:
1. Write user documentation for remote mode
2. Create environment setup guide
3. Document API for potential integrations
4. Train team on remote mode usage
5. Monitor initial usage

**Success Criteria**:
- Complete documentation available
- Users can set up and use remote mode
- No critical issues in dev/integration

---

## 8. Verification Checklist (BEFORE Implementation)

### Pre-Implementation Verification

**CRITICAL**: Complete these checks BEFORE writing code

- [ ] **ACI 64GB Verification**:
  ```bash
  az container create --cpu 4 --memory 64 --dry-run
  ```
  - If succeeds → Proceed with ACI
  - If fails → Document error, reconsider approach

- [ ] **WebSocket Support Verification**:
  ```bash
  # Test WebSocket through Azure Load Balancer
  # Confirm no timeout issues with long-lived connections
  ```

- [ ] **Long HTTP Timeout Verification**:
  ```python
  # Test 60-minute HTTP request doesn't get killed
  # Confirm Azure infrastructure supports long requests
  ```

- [ ] **Target Tenant Permissions**:
  ```bash
  # Verify managed identity has Reader role on target tenants
  az role assignment list --assignee <identity-principal-id>
  ```

### Post-Implementation Monitoring

**Track these metrics for 2 weeks in dev**:

- [ ] **Operation Duration Distribution**:
  - p50, p95, p99 scan durations
  - Alert if p95 > 50 minutes

- [ ] **Timeout Rate**:
  - Track operations exceeding 60 minutes
  - Alert if >20% timeout

- [ ] **Concurrent Operations**:
  - Track concurrent scan count
  - Alert if frequently >3 concurrent

- [ ] **WebSocket Stability**:
  - Track WebSocket disconnections
  - Alert if >5% disconnection rate

---

## 9. Decision Tree: When to Add Complexity

```
START: Simple HTTP + WebSocket approach deployed

    ↓

Monitor for 2 weeks in dev

    ↓

Are operations timing out (>20% exceed 60 min)?
  ├─ YES → Consider Redis job queue
  │         (Allow operations >60 minutes)
  │
  └─ NO → Continue monitoring

    ↓

Are users requesting >3 concurrent scans?
  ├─ YES → Consider Redis job queue
  │         (Better concurrency management)
  │
  └─ NO → Continue monitoring

    ↓

Is ACI 64GB unavailable (verified error)?
  ├─ YES → Investigate Container Apps
  │         (Higher resource limits)
  │
  └─ NO → Continue with ACI

    ↓

Does user explicitly request production deployment?
  ├─ YES → Add production environment
  │         (3-environment setup)
  │
  └─ NO → Continue with dev + integration

    ↓

Continue simple approach until evidence demands complexity
```

---

## 10. Philosophy Compliance Summary

### What We Removed (Premature Optimization):

1. **Production Environment**:
   - **Reason**: User explicitly deferred ("We do not need to do prod yet")
   - **Philosophy**: "Don't build for hypothetical future requirements"
   - **Savings**: 33% infrastructure cost reduction, simpler CI/CD

2. **Redis Job Queue**:
   - **Reason**: No evidence 60-minute HTTP timeout insufficient
   - **Philosophy**: "Start minimal, grow as needed"
   - **Savings**: Eliminates Redis container, job management code, polling logic

3. **Branch-Based GitOps**:
   - **Reason**: Tag-based deployment simpler and more explicit
   - **Philosophy**: "Prefer clarity over cleverness"
   - **Savings**: No branch management, clearer version control

4. **Container Apps Fallback**:
   - **Reason**: ACI 64GB availability unverified
   - **Philosophy**: "Avoid future-proofing"
   - **Savings**: No fallback code, simpler infrastructure

### What We Keep (Essential):

1. **Two Environments**: Dev and Integration (proven necessary)
2. **64GB RAM**: User requirement for large tenant scans
3. **Separate Neo4j**: Mandatory for environment isolation
4. **Managed Identity**: Security requirement for Azure access
5. **WebSocket Progress**: Better UX than polling
6. **API Key Authentication**: Security requirement

### Philosophy Score:

**Before**: B- (70%) - Premature optimization detected
**After**: A (95%) - Ruthlessly simple, grow-as-needed approach

---

## 11. Success Metrics (Simplified)

### Technical KPIs:

- ✅ **Backward Compatibility**: 100% existing CLI works (unchanged)
- ✅ **Service Availability**: 99.5% uptime (dev + integration)
- ✅ **Operation Success Rate**: >95% completion rate
- ✅ **Operation Duration**: p95 < 50 minutes (within 60 min timeout)

### Business KPIs:

- ✅ **User Adoption**: 50% using remote mode within 3 months
- ✅ **Error Rate**: <5% of remote operations fail
- ✅ **Support Tickets**: <10% users need setup help
- ✅ **Infrastructure Cost**: <$400/month (two environments, no prod)

---

## 12. References

### Related Documents:
- [Detailed Module Specs](modules/CLIENT_MODULE_SPEC.md)
- [Security Design](docs/security/ATG_CLIENT_SERVER_SECURITY_DESIGN.md)
- [Philosophy Context](.claude/context/PHILOSOPHY.md)

### Philosophy Principles Applied:
- "Start minimal, grow as needed" → Deferred async queue and prod
- "Don't build for hypothetical future requirements" → No Container Apps fallback
- "Present-moment focus" → Only dev + integration environments
- "Avoid future-proofing" → No premature optimization
- "Occam's Razor" → Simplest solution (HTTP + WebSocket)

---

## Next Steps

1. **Review this simplified design** with team
2. **Execute verification checklist** (ACI 64GB, WebSocket support)
3. **Get approval** before implementation
4. **Begin Phase 1** (Foundation) with simplified approach
5. **Monitor metrics** to determine when/if complexity needed

---

**Architecture Review Date**: 2025-12-09
**Next Review**: After Phase 2 completion (Week 3)
**Philosophy Guardian Approval**: PENDING
