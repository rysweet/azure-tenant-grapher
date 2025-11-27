# Azure Tenant Grapher - Documentation Index

## Issue #502: Tenant Replication Improvements

### Deployment Guide
- **[TENANT_REPLICATION_DEPLOYMENT_GUIDE.md](TENANT_REPLICATION_DEPLOYMENT_GUIDE.md)** - Complete deployment guide for Issue #502 and 16 bug fixes. Covers overview, step-by-step deployment, expected results, troubleshooting, and rollback procedures.

### Technical Documentation
- **[BUG_59_DOCUMENTATION.md](BUG_59_DOCUMENTATION.md)** - Deep dive: Subscription ID abstraction in properties
- **[BUG_68_DOCUMENTATION.md](BUG_68_DOCUMENTATION.md)** - Deep dive: Provider name case sensitivity fix

## Iteration 8 Session (November 23, 2025)

### Session Reports
- **[ITERATION_8_RESULTS.md](ITERATION_8_RESULTS.md)** - Complete session report with metrics and timeline
- **[deployment_summary.md](deployment_summary.md)** - Quick reference summary

### Technical Documentation
- **[BUG_59_DOCUMENTATION.md](BUG_59_DOCUMENTATION.md)** - Deep dive on subscription ID abstraction fix (root cause)
- **[DEPLOYMENT_TROUBLESHOOTING.md](DEPLOYMENT_TROUBLESHOOTING.md)** - Common issues and solutions

### Quick Start Guides  
- **[QUICK_START_ITERATION_9.md](QUICK_START_ITERATION_9.md)** - Resume deployment after auth refresh

### Scripts
- `/tmp/RESUME_DEPLOYMENT.sh` - Automated deployment resume script

## Bug Fixes

### November 23, 2025
- **Bug #59**: Subscription ID abstraction (ROOT CAUSE) - commit faeb284
- **Bug #58**: Skip NIC NSG validation - commit 7651fde  
- **Bug #57**: NIC NSG deprecated field - commit 2011688

## Key Achievements

### Terraform Validation
| Metric | Value |
|--------|-------|
| Starting Errors | 6,457 |
| Final Errors | **0** ✅ |
| Iterations | 8 |
| Bug Fixes | 3 |

### Deployment
- **Resources Planned**: 3,569
- **Validation Success**: 100%
- **Architecture Validated**: Dual-graph abstraction works end-to-end

## See Also
- `../CLAUDE.md` - Project instructions and context
- `NEO4J_SCHEMA_REFERENCE.md` - Graph database schema  
- `DUAL_GRAPH_QUERIES.cypher` - Useful queries for dual-graph architecture

