# Azure Tenant Grapher - Documentation Index

## Issue #610: Autonomous Deployment with Goal-Seeking Agent

### Overview
- **[AUTONOMOUS_DEPLOYMENT_INDEX.md](AUTONOMOUS_DEPLOYMENT_INDEX.md)** ⭐ - **COMPLETE**: Comprehensive documentation index for autonomous deployment feature. AI-powered goal-seeking agent automatically recovers from deployment errors through iterative fix-and-retry cycles.

### User Documentation
- **[Tutorial: Your First Autonomous Deployment](quickstart/AGENT_DEPLOYMENT_TUTORIAL.md)** - 15-minute step-by-step walkthrough with real examples from IaC generation to deployed resources
- **[Autonomous Deployment Guide](guides/AUTONOMOUS_DEPLOYMENT.md)** - Complete user guide covering all command-line options, usage scenarios, and best practices
- **[Autonomous Deployment FAQ](guides/AUTONOMOUS_DEPLOYMENT_FAQ.md)** - Frequently asked questions about agent mode, troubleshooting, and configuration
- **[Agent vs Manual Deployment](guides/AGENT_VS_MANUAL_DEPLOYMENT.md)** - Decision guide comparing agent mode and manual deployment with real-world scenarios

### Technical Documentation
- **[Agent Deployer Reference](design/AGENT_DEPLOYER_REFERENCE.md)** - Complete technical specification including architecture, API reference, testing strategy, and performance considerations

### Key Features
- AI-powered autonomous error recovery (Claude SDK AutoMode)
- Iterative deployment loop (max 5 iterations, 300s timeout)
- Comprehensive deployment reports with full iteration history
- Works with all IaC formats (Terraform, Bicep, ARM)
- Automatic fixes for: provider registration, SKU availability, network conflicts, naming collisions

## Issue #570: SCAN_SOURCE_NODE Preservation Fix

### Fix Summary
- **[SCAN_SOURCE_NODE_FIX_SUMMARY.md](SCAN_SOURCE_NODE_FIX_SUMMARY.md)** ⭐ - **FIX DEPLOYED**: Layer operations now preserve SCAN_SOURCE_NODE relationships, resolving deployment blocker (900+ false positives eliminated). Includes technical details, migration paths, and complete documentation index.

## Issue #502: Tenant Replication Improvements

### Deployment Status
- **[ISSUE_502_DEPLOYMENT_READY.md](ISSUE_502_DEPLOYMENT_READY.md)** ⭐ - **DEPLOYMENT READY**: Terraform validation complete (0 errors), 1,268 import blocks verified, 99.3% resource support achieved. Awaiting Azure credential refresh.

### Deployment Guide
- **[TENANT_REPLICATION_DEPLOYMENT_GUIDE.md](TENANT_REPLICATION_DEPLOYMENT_GUIDE.md)** - Complete deployment guide for Issue #502 and 16 bug fixes. Covers overview, step-by-step deployment, expected results, troubleshooting, and rollback procedures.

### Bug Documentation (Terraform Validation - November 27, 2025)
- **[BUG_87_DOCUMENTATION.md](BUG_87_DOCUMENTATION.md)** ⭐ - Smart Detector Alert Rules location field fix. Impact: Fixed 72 terraform validation errors. Result: Part of achieving 0 configuration errors.
- **[BUG_88_DOCUMENTATION.md](BUG_88_DOCUMENTATION.md)** ⭐ - Action group resource ID case sensitivity fix. Impact: Fixed ALL remaining 72 terraform errors. Result: 0 total configuration errors!

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

### December 18, 2025
- **[Bug #10](BUG_10_DOCUMENTATION.md)** ⭐ - Child resources missing import blocks. Impact: Fixed 110/177 missing import blocks (from 37.9% to 100% coverage). Uses dual-graph original_id instead of config reconstruction.

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

## Architecture Documentation

### Dual-Graph Architecture
- **[architecture/scan-source-node-relationships.md](architecture/scan-source-node-relationships.md)** - SCAN_SOURCE_NODE relationship preservation in layer operations (Bug #117 fix). Explains why these relationships are critical for IaC generation and smart import validation.
- **[guides/scan-source-node-migration.md](guides/scan-source-node-migration.md)** - Migration guide for layers and archives created before Bug #117 fix. Includes detection, migration paths, and verification steps.
- **[quickstart/scan-source-node-quick-ref.md](quickstart/scan-source-node-quick-ref.md)** - Quick reference for developers: essential queries, Python API examples, common mistakes, and debugging checklist.

### Terraform Import Blocks
- **[concepts/TERRAFORM_IMPORT_BLOCKS.md](concepts/TERRAFORM_IMPORT_BLOCKS.md)** ⭐ - **START HERE**: User-friendly explanation of Terraform import blocks, how ATG generates them, and why they matter. Covers parent vs child resources, cross-tenant translation, and common questions.
- **[guides/TERRAFORM_IMPORT_TROUBLESHOOTING.md](guides/TERRAFORM_IMPORT_TROUBLESHOOTING.md)** ⭐ - Complete troubleshooting guide for missing or broken Terraform import blocks. Covers verification, diagnostics, and fixes for all common issues.
- **[quickstart/terraform-import-quick-ref.md](quickstart/terraform-import-quick-ref.md)** - Quick reference: commands, one-liners, and common fixes for import blocks.
- **[patterns/IMPORT_FIRST_STRATEGY.md](patterns/IMPORT_FIRST_STRATEGY.md)** - Why "import first, create second" eliminates deployment conflicts.

## See Also
- `../CLAUDE.md` - Project instructions and context
- `NEO4J_SCHEMA_REFERENCE.md` - Graph database schema
- `DUAL_GRAPH_QUERIES.cypher` - Useful queries for dual-graph architecture
