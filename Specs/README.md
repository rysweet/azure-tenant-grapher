# ATG Client-Server Architecture Specifications

**Project**: Azure Tenant Grapher Remote Execution
**Version**: 1.0
**Date**: 2025-12-09
**Status**: ✅ APPROVED FOR IMPLEMENTATION

---

## 📖 Quick Navigation

This directory contains the complete architectural specifications for transforming ATG from a CLI-only tool into a client-server system with remote execution capabilities.

### 🎯 Start Here

**New to this project?** Read documents in this order:

1. **[ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md)** ⭐ *Start here!*
   - Executive summary
   - System overview
   - Key design decisions
   - Module boundaries
   - Success metrics

2. **[ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt)** 📊
   - Visual ASCII diagrams
   - Data flow illustrations
   - Component interactions
   - Implementation phases

3. **[ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md)** 📋
   - Complete system architecture
   - API specifications
   - Integration strategy
   - Migration plan

### 📚 Detailed Specifications

#### Module Specifications

Located in `modules/` directory:

- **[CLIENT_MODULE_SPEC.md](modules/CLIENT_MODULE_SPEC.md)**
  - RemoteClient implementation
  - ExecutionDispatcher routing
  - Request/response models
  - Error handling patterns
  - Client-side testing

- **[SERVER_MODULE_SPEC.md](modules/SERVER_MODULE_SPEC.md)**
  - FastAPI service design
  - Job queue architecture
  - Job executor implementation
  - Authentication & authorization
  - Server-side testing

#### Operations Documentation

- **[DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md)**
  - Azure Container deployment
  - Infrastructure as Code (Bicep)
  - CI/CD pipeline (GitHub Actions)
  - Risk analysis and mitigation
  - Disaster recovery procedures
  - Operational runbook

---

## 🗺️ Document Map

### By Role

**For Developers**:
1. Start: [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md)
2. Implementation: [modules/CLIENT_MODULE_SPEC.md](modules/CLIENT_MODULE_SPEC.md), [modules/SERVER_MODULE_SPEC.md](modules/SERVER_MODULE_SPEC.md)
3. Reference: [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md)

**For DevOps Engineers**:
1. Start: [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md)
2. Visual: [ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt)
3. Reference: [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 5 & 13)

**For Product Managers**:
1. Executive Summary: [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md)
2. Benefits: [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 12)
3. Timeline: [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md) (Implementation Phases)

**For Security Team**:
1. Security Model: [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 6)
2. Risk Analysis: [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) (Section 5)
3. Operations: [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) (Section 8)

### By Topic

**Architecture Overview**:
- [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md) - Executive summary
- [ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt) - Visual diagrams
- [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Sections 1-2) - Detailed architecture

**API Design**:
- [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 2.2) - API endpoints
- [modules/SERVER_MODULE_SPEC.md](modules/SERVER_MODULE_SPEC.md) - Complete API reference

**Data Flow**:
- [ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt) - Flow diagrams
- [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 3) - Data flow specs

**Module Design**:
- [modules/CLIENT_MODULE_SPEC.md](modules/CLIENT_MODULE_SPEC.md) - Client module
- [modules/SERVER_MODULE_SPEC.md](modules/SERVER_MODULE_SPEC.md) - Server module
- [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 2) - All components

**Deployment**:
- [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) (Sections 1-4) - Infrastructure
- [ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt) - Environment architecture

**Security**:
- [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 6) - Security model
- [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) (Section 8) - Security hardening

**Operations**:
- [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) (Section 7) - Runbook
- [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) (Section 6) - Disaster recovery

**Testing**:
- [modules/CLIENT_MODULE_SPEC.md](modules/CLIENT_MODULE_SPEC.md) - Client testing
- [modules/SERVER_MODULE_SPEC.md](modules/SERVER_MODULE_SPEC.md) - Server testing
- [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 8) - Testing strategy

**Risk Management**:
- [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) (Section 5) - Risk analysis
- [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 11) - Mitigation

**Implementation Plan**:
- [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md) - Phase overview
- [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (Section 10) - Detailed phases

---

## 🎯 Key Design Decisions

| Decision | Document | Section |
|----------|----------|---------|
| REST API vs gRPC | [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) | 1.1 |
| Redis for job queue | [modules/SERVER_MODULE_SPEC.md](modules/SERVER_MODULE_SPEC.md) | Job Queue |
| Async jobs with polling | [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) | 3.1 |
| Backward compatibility | [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md) | Module Architecture |
| Zero changes to ATG core | [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) | 4.1 |
| Azure Container Instances | [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) | 1.1 |
| Three-environment strategy | [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) | 4.1 |

---

## 🏗️ Module Structure

All modules follow the **Brick Philosophy** with clear boundaries:

```
ATG Client-Server Architecture
│
├── Client Module (src/client/)
│   ├── RemoteClient - REST API client
│   ├── ExecutionDispatcher - Local vs remote routing
│   └── ATGClientConfig - Configuration
│
├── Server Module (src/server/)
│   ├── FastAPI App - REST API endpoints
│   ├── Authentication - API key verification
│   └── Middleware - Logging, rate limiting
│
├── Job Queue Module (src/server/jobs/)
│   ├── JobQueue - Redis-backed queue
│   ├── JobExecutor - Wraps ATG services
│   └── BackgroundWorker - Concurrent execution
│
└── Existing ATG Core (unchanged)
    ├── AzureTenantGrapher
    ├── AzureDiscoveryService
    ├── ResourceProcessingService
    └── IaC Emitters
```

**Detailed specs**: See `modules/` directory

---

## 📋 Implementation Phases

### Phase 1: Foundation (Week 1-2)
- Create client and server modules
- Implement authentication
- Unit tests

**Deliverable**: Client can connect to server with auth

### Phase 2: Job Queue (Week 2-3)
- Redis job queue
- Job executor
- Integration tests

**Deliverable**: Async job execution with status tracking

### Phase 3: CLI Integration (Week 3-4)
- Add `--remote` flag
- Progress display
- All commands work remotely

**Deliverable**: End-to-end scan via remote service

### Phase 4: Deployment (Week 4-5)
- Dockerfile and Bicep templates
- GitHub Actions workflows
- Three environments

**Deliverable**: Service deployed to all environments

### Phase 5: Rollout (Week 5-6)
- Documentation
- Operational runbook
- Gradual rollout

**Deliverable**: 50%+ users on remote mode, <5% error rate

**Complete timeline**: [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md)

---

## 🎓 Learning Path

### Day 1: Understanding the Vision
1. Read [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md) (15 min)
2. Review [ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt) (10 min)
3. Understand the problem and solution

### Day 2: Diving Deep
1. Read [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md) (45 min)
2. Review module boundaries and contracts
3. Understand data flows

### Day 3: Implementation Details
1. Read [modules/CLIENT_MODULE_SPEC.md](modules/CLIENT_MODULE_SPEC.md) (30 min)
2. Read [modules/SERVER_MODULE_SPEC.md](modules/SERVER_MODULE_SPEC.md) (30 min)
3. Review code examples and patterns

### Day 4: Operations & Deployment
1. Read [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md) (45 min)
2. Review infrastructure diagrams
3. Understand CI/CD pipeline

### Day 5: Ready to Build
1. Choose a Phase 1 task
2. Review relevant module spec
3. Start implementation

---

## 🔍 Quick Reference

### Key Endpoints

```
POST   /api/v1/scan                 # Submit scan job
GET    /api/v1/jobs/{id}            # Get job status
GET    /api/v1/jobs/{id}/result     # Get job result
GET    /api/v1/jobs/{id}/artifacts  # Download artifacts
POST   /api/v1/generate-iac         # Generate IaC
POST   /api/v1/create-tenant        # Create tenant
DELETE /api/v1/jobs/{id}            # Cancel job
GET    /api/v1/health               # Health check
```

### Environment Variables

**Client-Side**:
```bash
ATG_REMOTE_MODE=true
ATG_SERVICE_URL=https://atg-service-dev.azurecontainer.io
ATG_API_KEY=your-api-key
```

**Server-Side**:
```bash
ATG_TARGET_TENANT_ID=tenant-id
REDIS_URL=redis://localhost:6379
NEO4J_URI=bolt://localhost:7687
ATG_API_KEYS=key1,key2,key3
```

### CLI Usage

```bash
# Local mode (default)
atg scan --tenant-id X

# Remote mode
atg scan --tenant-id X --remote

# Or set environment variable
export ATG_REMOTE_MODE=true
atg scan --tenant-id X
```

---

## ✅ Architecture Approval Checklist

- ✅ Technical feasibility validated
- ✅ Backward compatibility ensured
- ✅ Security model reviewed
- ✅ Deployment strategy defined
- ✅ Risk mitigation planned
- ✅ Testing strategy complete
- ✅ Operations runbook ready
- ✅ Module specifications complete
- ✅ Data flows documented
- ✅ Integration points identified

**Status**: APPROVED FOR IMPLEMENTATION

**Next Step**: Begin Phase 1 (Foundation)

---

## 📞 Getting Help

### Questions About...

**Architecture Decisions**: See [ATG_CLIENT_SERVER_ARCHITECTURE.md](ATG_CLIENT_SERVER_ARCHITECTURE.md)

**Implementation Details**: Check `modules/` specs

**Deployment**: Reference [DEPLOYMENT_AND_RISK_MITIGATION.md](DEPLOYMENT_AND_RISK_MITIGATION.md)

**Operations**: Consult operational runbook (Section 7)

### Document Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-09 | Initial architecture approved |

---

## 🎨 Philosophy Alignment

This architecture follows the ATG project philosophy:

- **Ruthless Simplicity**: No unnecessary abstractions
- **Modular Design**: Each module is a self-contained "brick"
- **Zero-BS Implementation**: Every function works or doesn't exist
- **Regeneratable**: Complete specs enable rebuilding from scratch
- **Backward Compatible**: Local mode unchanged
- **Trust in Emergence**: Complex system from simple components

**Philosophy Reference**: `../.claude/context/PHILOSOPHY.md`

---

## 🚀 Ready to Start?

1. **Read**: [ARCHITECTURE_SUMMARY.md](ARCHITECTURE_SUMMARY.md)
2. **Understand**: [ARCHITECTURE_DIAGRAM.txt](ARCHITECTURE_DIAGRAM.txt)
3. **Implement**: Begin Phase 1 tasks
4. **Reference**: Use module specs as needed

**Target**: Phase 1 complete by Week 2

Good luck, and happy coding! 🏴‍☠️
