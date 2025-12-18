# ATG Client-Server Architecture - Executive Summary

**Project**: Azure Tenant Grapher Remote Execution
**Version**: 1.0
**Date**: 2025-12-09
**Status**: ✅ APPROVED FOR IMPLEMENTATION

---

## 📋 Document Index

This architecture consists of four comprehensive specification documents:

1. **[ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md)** (Main Architecture)
   - System overview and component interactions
   - High-level design decisions
   - Data flow specifications
   - Integration points with existing ATG
   - Complete API reference

2. **[modules/CLIENT_MODULE_SPEC.md](modules/CLIENT_MODULE_SPEC.md)** (Client Specification)
   - RemoteClient implementation details
   - ExecutionDispatcher routing logic
   - Request/response models
   - Error handling patterns
   - Testing requirements

3. **[modules/SERVER_MODULE_SPEC.md](modules/SERVER_MODULE_SPEC.md)** (Server Specification)
   - FastAPI service architecture
   - Job queue implementation (Redis)
   - Job executor wrapping existing ATG services
   - Authentication and authorization
   - Background worker processes

4. **[DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md)** (Operations)
   - Azure Container Instance deployment
   - Infrastructure as Code (Bicep)
   - CI/CD pipeline (GitHub Actions)
   - Risk analysis and mitigation strategies
   - Disaster recovery procedures
   - Operational runbook

---

## 🎯 Architecture at a Glance

### System Overview

```
┌─────────────┐         REST API          ┌──────────────────┐
│  ATG CLI    │────────(HTTPS/Jobs)───────►│   ATG Service    │
│  (Client)   │◄──────(Status/Results)─────│   (FastAPI)      │
└─────────────┘                            └──────────────────┘
      │                                            │
      │ Local Mode                                 │
      │ (backward compat)                          │
      ▼                                            ▼
┌─────────────┐                           ┌──────────────────┐
│  Existing   │                           │  Job Queue       │
│  ATG Core   │◄──────────────────────────│  (Redis)         │
│  Services   │      Direct Usage         └──────────────────┘
└─────────────┘                                    │
                                                   ▼
                                          ┌──────────────────┐
                                          │  Job Executor    │
                                          │  (wraps ATG)     │
                                          └──────────────────┘
                                                   │
                                                   ▼
                                          ┌──────────────────┐
                                          │  Neo4j + Azure   │
                                          └──────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **REST API** (not gRPC/GraphQL) | Simplicity, HTTP tooling, firewall-friendly |
| **Redis Job Queue** | Proven reliability, simple persistence, fast |
| **Async Jobs with Polling** | Better than WebSockets for long operations (hours) |
| **Backward Compatible CLI** | Zero breaking changes, remote mode opt-in |
| **Zero Changes to ATG Core** | Services used as-is by job executor |
| **FastAPI** | Modern async Python framework, auto-docs |
| **Azure Container Instances** | Simplicity over AKS, 64GB+ RAM support |
| **Three Environments** | Dev/Int/Prod isolation, separate target tenants |

---

## 📦 Module Architecture (Brick Philosophy)

All modules follow the **brick philosophy** with clear boundaries:

### 1. Client Module (`src/client/`)

**Responsibility**: CLI communication with remote service

**Public API (Studs)**:
- `RemoteClient`: REST API client
- `ExecutionDispatcher`: Local vs remote routing
- `ATGClientConfig`: Client configuration

**Contract**:
- **Inputs**: Service URL, API key, command parameters
- **Outputs**: Job IDs, status objects, results
- **Side Effects**: Network requests, file downloads
- **Dependencies**: `httpx`, existing CLI commands

**Key Features**:
- Retry logic with exponential backoff
- Progress polling with rich display
- Artifact downloads (IaC files)
- Health checks
- Backward compatible (local mode unchanged)

### 2. Server Module (`src/server/`)

**Responsibility**: REST API for ATG operations

**Public API (Studs)**:
- `POST /api/v1/scan`: Submit scan job
- `GET /api/v1/jobs/{id}`: Get job status
- `GET /api/v1/jobs/{id}/result`: Get results
- `GET /api/v1/jobs/{id}/artifacts`: Download files
- `POST /api/v1/generate-iac`: IaC generation
- `POST /api/v1/create-tenant`: Tenant creation

**Contract**:
- **Inputs**: HTTP requests with API key auth
- **Outputs**: Job IDs, status updates, results
- **Side Effects**: Job queue ops, DB writes, Azure calls
- **Dependencies**: `fastapi`, `redis`, existing ATG services

**Key Features**:
- API key authentication
- Rate limiting
- Graceful shutdown
- Health checks
- Metrics endpoint

### 3. Job Queue Module (`src/server/jobs/`)

**Responsibility**: Async job processing

**Public API (Studs)**:
- `JobQueue`: Redis-backed queue operations
- `JobExecutor`: Wraps existing ATG services
- `BackgroundWorker`: Process jobs concurrently

**Contract**:
- **Inputs**: Job parameters, status updates
- **Outputs**: Job objects, status info
- **Side Effects**: Redis operations, ATG service calls
- **Dependencies**: `redis`, existing ATG services

**Key Features**:
- Persistent job state (survives restarts)
- Progress tracking
- Error handling with retry
- Concurrent job execution (configurable limit)
- Job result storage

---

## 🔄 Data Flow Examples

### Scan Operation (Remote Mode)

```
1. User: atg scan --tenant-id X --remote
   └─► CLI detects remote mode from config

2. CLI → Service: POST /api/v1/scan
   └─► Service: Returns job_id="abc123"

3. CLI polls every 5s: GET /api/v1/jobs/abc123
   └─► Service: {status: "running", progress: 45%}

4. Service → Job Queue: Enqueue job
   └─► Worker picks up job
       └─► Calls AzureTenantGrapher.build_graph()
           └─► Discovers resources from Azure
           └─► Stores in Neo4j
           └─► Updates job progress

5. CLI polls again: GET /api/v1/jobs/abc123
   └─► Service: {status: "completed"}

6. CLI: GET /api/v1/jobs/abc123/result
   └─► Service: {resources: 902, success: true}

7. CLI displays results to user
```

### IaC Generation (Remote Mode)

```
1. User: atg generate-iac --remote
   └─► CLI submits job

2. Service enqueues IaC generation job
   └─► Worker executes:
       • Query Neo4j for resources
       • Run IaC traverser
       • Generate Terraform files
       • Store artifacts in /tmp/atg-jobs/{job_id}/

3. CLI polls for completion

4. CLI: GET /api/v1/jobs/{id}/artifacts
   └─► Service: Returns zip of generated files

5. CLI downloads and extracts artifacts locally
```

---

## 🏗️ Deployment Architecture

### Three-Environment Strategy

```
GitHub Branches → Environments → Target Tenants
─────────────────────────────────────────────────
main         →  Dev          →  DefenderATEVET17
integration  →  Integration  →  Target Tenant A
prod         →  Production   →  Target Tenant B
```

### Azure Resources Per Environment

Each environment consists of:

1. **Container Group** (Azure Container Instances)
   - ATG API container (4 CPU, 64GB RAM)
   - Neo4j container (2 CPU, 32GB RAM)
   - Redis container (1 CPU, 4GB RAM)

2. **Storage Account**
   - Azure File Share for Neo4j data (1TB)
   - Blob container for artifacts

3. **Key Vault**
   - API keys
   - Neo4j password
   - Service principal secrets

4. **Managed Identity**
   - Reader permissions on target tenant
   - Key Vault access

5. **Virtual Network**
   - Container subnet
   - Storage subnet (private endpoints)

### GitHub Actions CI/CD

**Workflow**:
```
Push to branch
  ↓
Build Docker image
  ↓
Push to ghcr.io
  ↓
Deploy Bicep templates
  ↓
Wait for health check
  ↓
Run smoke tests
  ↓
Send notification
```

---

## 🔒 Security Model

### Authentication Flow

```
Client                Service              Key Vault
  │                     │                     │
  │──1. Request─────────►│                    │
  │   (Bearer token)     │                    │
  │                      │──2. Load keys──────►│
  │                      │◄──3. Keys──────────│
  │                      │                     │
  │                      │──4. Verify token    │
  │◄─5. Response────────│                     │
```

### Azure Resource Access

```
ATG Service Container
  │
  └──► Managed Identity
          │
          └──► Target Tenant (Reader role)
          │
          └──► Key Vault (Secrets Get)
          │
          └──► Storage Account (Blob Write)
```

### Key Rotation (Zero Downtime)

```
1. Generate new API key (key3)
2. Add key3 to Key Vault
3. Service reads keys: [key1, key2, key3]
4. Distribute key3 to clients
5. Remove key1 from Key Vault
6. Service now accepts: [key2, key3]
```

---

## 🛡️ Risk Mitigation Summary

| Risk | Mitigation | Monitoring |
|------|------------|------------|
| **Breaking CLI** | Opt-in remote mode, extensive tests | CLI success rate tracking |
| **Service downtime** | Multi-env, auto-restart, health checks | Uptime monitoring, alerts |
| **API rate limits** | Job queue, concurrency limits, backoff | Azure API call metrics |
| **Auth compromise** | Key rotation, Key Vault, separate keys per env | Audit logging, anomaly detection |
| **DB corruption** | Daily backups, separate DBs, point-in-time recovery | Backup job monitoring |
| **Job queue overflow** | Queue depth limits, job timeout, max concurrent | Queue depth alerts |

**Rollback Strategy**:
1. Immediate: Set `ATG_REMOTE_MODE=false` (local mode)
2. Short-term: Disable remote mode in CLI defaults
3. Long-term: Remove remote code (isolated modules)

---

## 📈 Success Metrics

### Technical KPIs

- ✅ **Backward Compatibility**: 100% existing CLI commands work unchanged
- ✅ **Service Availability**: 99.5% uptime
- ✅ **Job Success Rate**: >95% completion rate
- ✅ **API Latency**: p95 <200ms for status checks
- ✅ **Remote Scan Duration**: Within 20% of local mode

### Business KPIs

- ✅ **User Adoption**: 50% using remote mode within 3 months
- ✅ **Error Rate**: <5% of remote operations fail
- ✅ **Support Tickets**: <10% users need help with setup
- ✅ **Infrastructure Cost**: <$500/month per environment

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal**: Core client-server infrastructure

**Deliverables**:
- `src/client/` module (RemoteClient, ExecutionDispatcher)
- `src/server/` module (FastAPI app skeleton)
- API authentication
- Configuration management
- Unit tests

**Success**: Client can connect to server with auth

---

### Phase 2: Job Queue (Week 2-3)
**Goal**: Async job processing

**Deliverables**:
- Redis job queue implementation
- Job executor wrapping ATG services
- Background workers
- Job status endpoints
- Integration tests

**Success**: Jobs execute asynchronously with status tracking

---

### Phase 3: CLI Integration (Week 3-4)
**Goal**: Remote mode in CLI

**Deliverables**:
- `--remote` flag support
- Progress display for remote jobs
- All CLI commands work in remote mode
- Documentation updates

**Success**: End-to-end scan via remote service

---

### Phase 4: Deployment (Week 4-5)
**Goal**: Azure Container deployment

**Deliverables**:
- Dockerfile and Bicep templates
- GitHub Actions workflows
- Three environments configured
- Monitoring and alerts
- Smoke tests

**Success**: Service deployed to all environments

---

### Phase 5: Rollout (Week 5-6)
**Goal**: Production readiness

**Deliverables**:
- User documentation
- Operational runbook
- Team training
- Gradual rollout (10% → 50% → 100%)
- Performance optimization

**Success**: 50%+ users on remote mode, <5% error rate

---

## 🧪 Testing Strategy

### Test Coverage by Phase

**Phase 1 - Foundation**:
- Unit tests: Client module (5 tests)
- Unit tests: Server API (8 tests)
- Unit tests: Authentication (4 tests)

**Phase 2 - Job Queue**:
- Unit tests: Job queue operations (6 tests)
- Unit tests: Job executor (5 tests)
- Integration tests: Job lifecycle (3 tests)

**Phase 3 - CLI Integration**:
- Integration tests: CLI commands (10 tests)
- E2E tests: Full scan workflow (2 tests)

**Phase 4 - Deployment**:
- Smoke tests: Health checks (3 tests)
- Smoke tests: Basic operations (5 tests)
- Load tests: Concurrent jobs (2 tests)

**Phase 5 - Rollout**:
- User acceptance testing
- Performance benchmarking
- Security audit

---

## 📚 Related Documentation

### Internal References
- [Existing ATG Architecture](../docs/ARCHITECTURE_IMPROVEMENTS.md)
- [Neo4j Schema](../docs/NEO4J_SCHEMA_REFERENCE.md)
- [Project Context](../.claude/context/PROJECT.md)

### External Standards
- [12 Factor App](https://12factor.net/) - Cloud-native principles
- [OpenAPI Specification](https://swagger.io/specification/) - API documentation
- [Semantic Versioning](https://semver.org/) - Version management

---

## ✅ Architecture Approval

This architecture has been reviewed and approved for implementation:

- ✅ **Technical Feasibility**: All components use proven technologies
- ✅ **Backward Compatibility**: Zero breaking changes to existing CLI
- ✅ **Security**: API keys, managed identity, audit logging
- ✅ **Scalability**: Job queue supports concurrent operations
- ✅ **Operational**: Comprehensive deployment and recovery procedures
- ✅ **Testing**: Clear test requirements per phase
- ✅ **Documentation**: Complete specifications for all modules

**Next Step**: Begin Phase 1 implementation (Foundation)

---

## 📞 Support & Questions

For questions about this architecture:
- **Design Decisions**: See individual specification documents
- **Implementation Details**: Check module specs in `Specs/modules/`
- **Deployment**: Reference `DEPLOYMENT_AND_RISK_MITIGATION.md`
- **Operations**: Consult operational runbook (Section 7)

**Architecture Review Date**: 2025-12-09
**Next Review**: After Phase 3 completion (Week 4)
