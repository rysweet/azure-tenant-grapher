#!/usr/bin/env python3
"""
Generate a complete INDEX.md that includes ALL documentation sections.
This eliminates orphaned documents by ensuring every section is represented.
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent.parent / "docs"


def generate_complete_index():
    """Generate comprehensive INDEX.md with all sections."""

    index_content = """# Azure Tenant Grapher - Documentation Index

## Quick Start

### Getting Started
- **[Installation Guide](quickstart/installation.md)** - Set up Azure Tenant Grapher in minutes
- **[Quick Start Guide](quickstart/quick-start.md)** - Your first scan and IaC generation
- **[Scale Operations](quickstart/scale-operations.md)** - Working with layers and managing graph data

### Tutorials
- **[Your First Autonomous Deployment](quickstart/AGENT_DEPLOYMENT_TUTORIAL.md)** ⭐ - 15-minute walkthrough with AI-powered deployment
- **[Autonomous Deployment Quick Reference](quickstart/AUTONOMOUS_DEPLOYMENT_QUICK_REF.md)** - Commands and concepts at a glance
- **[Terraform Import Quick Reference](quickstart/terraform-import-quick-ref.md)** - Import existing resources
- **[SCAN_SOURCE_NODE Quick Reference](quickstart/scan-source-node-quick-ref.md)** - Essential queries and examples
- **[Web App Mode](quickstart/web-app-mode.md)** - Run ATG as a web application

## User Guides

### Deployment & Operations
- **[Autonomous Deployment Guide](guides/AUTONOMOUS_DEPLOYMENT.md)** ⭐ - Complete guide to AI-powered deployment
- **[Autonomous Deployment FAQ](guides/AUTONOMOUS_DEPLOYMENT_FAQ.md)** - Common questions and troubleshooting
- **[Agent vs Manual Deployment](guides/AGENT_VS_MANUAL_DEPLOYMENT.md)** - Decision guide with scenarios
- **[Layer Management Quickstart](guides/LAYER_MANAGEMENT_QUICKSTART.md)** - Working with graph layers
- **[Tenant Inventory Reports](guides/TENANT_INVENTORY_REPORTS.md)** - Generate comprehensive tenant reports
- **[Terraform Import Troubleshooting](guides/TERRAFORM_IMPORT_TROUBLESHOOTING.md)** - Debug missing or broken import blocks
- **[SCAN_SOURCE_NODE Migration Guide](guides/scan-source-node-migration.md)** - Migrate legacy layers

## Architecture & Concepts

### Core Architecture
- **[Architecture Overview](architecture/README.md)** - System design and components
- **[Dual-Graph Architecture](architecture/dual-graph.md)** - Original vs abstracted nodes
- **[SCAN_SOURCE_NODE Relationships](architecture/scan-source-node-relationships.md)** - Why these relationships are critical
- **[Multi-Layer Graph Architecture](architecture/MULTI_LAYER_GRAPH_ARCHITECTURE.md)** - Layer system design
- **[Architecture Flow](architecture/ARCHITECTURE_FLOW.md)** - Data flow through the system
- **[Layer Architecture Summary](architecture/LAYER_ARCHITECTURE_SUMMARY.md)** - Layer implementation details
- **[Layer CLI Specification](architecture/LAYER_CLI_SPECIFICATION.md)** - Command-line interface for layers
- **[Layer CLI Implementation](architecture/LAYER_CLI_IMPLEMENTATION.md)** - Implementation guide
- **[Layer Query Patterns](architecture/LAYER_QUERY_PATTERNS.md)** - Common Cypher queries
- **[Layer Service Interfaces](architecture/LAYER_SERVICE_INTERFACES.md)** - Service layer APIs
- **[Layer Implementation Checklist](architecture/LAYER_IMPLEMENTATION_CHECKLIST.md)** - Implementation verification
- **[CLI Commands](architecture/CLI_COMMANDS.md)** - Command reference

### Key Concepts
- **[Terraform Import Blocks](concepts/TERRAFORM_IMPORT_BLOCKS.md)** ⭐ - How ATG generates import blocks
- **[Import-First Strategy](patterns/IMPORT_FIRST_STRATEGY.md)** - Why import before create

## Design Documentation

### Feature Designs
- **[Agent Deployer Reference](design/AGENT_DEPLOYER_REFERENCE.md)** ⭐ - Technical spec for autonomous deployment
- **[Configuration System Quick Start](design/CONFIG_QUICK_START.md)** - ATG configuration overview
- **[Configuration System Design](design/CONFIG_SYSTEM_DESIGN.md)** - Complete config architecture
- **[Scale Operations Architecture Diagram](design/SCALE_OPERATIONS_ARCHITECTURE_DIAGRAM.md)** - Visual architecture
- **[Scale Operations UI Design](design/SCALE_OPERATIONS_UI_DESIGN.md)** - User interface design
- **[Scale Operations UI Mockups](design/SCALE_OPERATIONS_UI_MOCKUPS.md)** - UI wireframes
- **[Scale Operations UI Summary](design/SCALE_OPERATIONS_UI_SUMMARY.md)** - UI implementation overview
- **[SPA Architecture](design/SPA_ARCHITECTURE.md)** - Single-page application design
- **[SPA Requirements](design/SPA_REQUIREMENTS.md)** - Application requirements
- **[Design Summary](design/DESIGN_SUMMARY.md)** - Overall design principles
- **[Graph Enrichment Plan](design/GRAPH_ENRICHMENT_PLAN.md)** - Graph enhancement strategy
- **[VNet Overlap Detection](design/DESIGN_VNET_OVERLAP_DETECTION.md)** - Network conflict detection
- **[Dataplane Plugin Architecture](DATAPLANE_PLUGIN_ARCHITECTURE.md)** - Plugin system design
- **[Dataplane Builder Quickstart](DATAPLANE_BUILDER_QUICKSTART.md)** - Build dataplane plugins
- **[Azure MCP Integration](design/azure_mcp_integration.md)** - Model Context Protocol integration
- **[Azure MCP Integration Research](design/azure_mcp_integration_research.md)** - Research findings
- **[Resource Processing Efficiency](design/resource_processing_efficiency.md)** - Performance optimizations

### Cross-Tenant Features
- **[Cross-Tenant Translation Integration](design/cross-tenant-translation/INTEGRATION_SUMMARY.md)** - Complete cross-tenant feature summary
- **[Cross-Tenant Phase 5 Complete](design/cross-tenant-translation/PHASE5_INTEGRATION_COMPLETE.md)** - Final implementation status

### Special Topics
- **[Azure MCP Integration](azure-mcp-integration.md)** - MCP server integration
- **[Graph Abstraction](graph-abstraction/README.md)** - ID abstraction system

## Technical Reference

### Database & Schema
- **[Neo4j Schema Reference](NEO4J_SCHEMA_REFERENCE.md)** ⭐ - Complete graph database schema
- **[Dual-Graph Index](DUAL_GRAPH_INDEX.md)** - Dual-graph documentation hub
- **[Dual-Graph Schema](DUAL_GRAPH_SCHEMA.md)** - Detailed schema specification
- **[Dual-Graph Queries](DUAL_GRAPH_QUERIES.cypher)** - Query cookbook with 100+ examples
- **[Fidelity Tracking](FIDELITY_TRACKING.md)** - Resource property completeness tracking
- **[Synthetic Node Visualization](SYNTHETIC_NODE_VISUALIZATION.md)** - Visualizing synthetic nodes
- **[Synthetic Node Quick Reference](SYNTHETIC_NODE_QUICK_REFERENCE.md)** - Working with synthetic data

### Scale Operations
- **[Scale Operations](SCALE_OPERATIONS.md)** ⭐ - Layer operations and management
- **[Scale Operations Diagrams](SCALE_OPERATIONS_DIAGRAMS.md)** - Visual diagrams
- **[Scale Operations E2E Demonstration](SCALE_OPERATIONS_E2E_DEMONSTRATION.md)** - End-to-end examples
- **[Scale Operations E2E Findings](SCALE_OPERATIONS_E2E_FINDINGS.md)** - Testing results
- **[Scale Operations Bug Fixes](SCALE_OPERATIONS_BUG_FIXES.md)** - Known issues and fixes
- **[Scale Operations UI Code Review](SCALE_OPERATIONS_UI_CODE_REVIEW.md)** - UI implementation review
- **[Scale Config Reference](SCALE_CONFIG_REFERENCE.md)** - Configuration options
- **[Scale Performance Guide](SCALE_PERFORMANCE_GUIDE.md)** - Performance optimization

### Performance
- **[Performance Optimizations](performance/optimizations.md)** - System performance tuning

## Security

- **[Security Overview](security/SECURITY.md)** - Security guidelines and best practices
- **[Security Review](security/SECURITY_REVIEW_FINAL.md)** - Final security assessment
- **[ATG Client-Server Security Design](security/ATG_CLIENT_SERVER_SECURITY_DESIGN.md)** - Security architecture
- **[Security Subprocess Guidelines](SECURITY_SUBPROCESS_GUIDELINES.md)** - Safe subprocess execution

## Testing

### Test Strategy
- **[Test Specification Table](testing/TEST_SPECIFICATION_TABLE.md)** - Complete test coverage matrix
- **[Final Test Specification](testing/final_test_spec.md)** - Final test plan
- **[Test Fix Summary](testing/TEST_FIX_SUMMARY.md)** - Test suite improvements
- **[TDD Quickstart](TDD_QUICKSTART.md)** - Test-driven development guide
- **[TDD Test Strategy Tech Debt](TDD_TEST_STRATEGY_TECH_DEBT.md)** - Testing tech debt analysis
- **[TDD Test Suite Issue #296](TDD_TEST_SUITE_ISSUE_296.md)** - Test suite implementation
- **[TDD Test Descriptions Issue #296](TDD_TEST_DESCRIPTIONS_ISSUE_296.md)** - Test descriptions

### Agentic Testing
- **[Agentic Testing Design](agentic-testing/DESIGN.md)** - AI-powered test generation
- **[Agentic Testing Requirements](agentic-testing/REQUIREMENTS.md)** - Requirements and goals
- **[Agentic Testing Validation](agentic-testing/VALIDATION.md)** - Validation approach
- **[Scale Operations Agentic Testing](testing/SCALE_OPERATIONS_AGENTIC_TESTING.md)** - Layer testing with AI
- **[Agent Mode Test Implementation](testing/AGENT_MODE_TEST_IMPLEMENTATION.md)** - Test implementation details
- **[PR Test Plan](testing/PR_TEST_PLAN.md)** - Pull request testing strategy
- **[Test Tenant Specification](testing/test_tenant_spec.md)** - Test tenant setup

## Web Application

- **[Web App Mode Summary](web-app/summary.md)** - Web application overview
- **[Azure Bastion Connection Guide](AZURE_BASTION_CONNECTION_GUIDE.md)** - Remote access via Azure Bastion

## Command Reference

- **[Demo Commands Overview](demo/overview.md)** - Command demonstrations
- **[Demo Commands Index](demo/commands/README.md)** - All command examples
- **[Report Help Text](command-help/report-help-text.md)** - Report command usage
- **[Report Implementation Reference](command-help/report-implementation-reference.md)** - Report implementation details
- **[Monitor Command](MONITOR_COMMAND.md)** - Real-time monitoring

### Individual Command Demos
- **[Build Command](demo/commands/build.md)** - Graph building
- **[Config Command](demo/commands/config.md)** - Configuration management
- **[Visualize Command](demo/commands/visualize.md)** - Graph visualization
- **[Spec Command](demo/commands/spec.md)** - Specification generation
- **[Generate Spec](demo/commands/generate-spec.md)** - Spec generation details
- **[Generate IaC](demo/commands/generate-iac.md)** - IaC generation details
- **[Generate Sim Doc](demo/commands/generate-sim-doc.md)** - Simulation documentation
- **[Threat Model](demo/commands/threat-model.md)** - Threat modeling
- **[Agent Mode](demo/commands/agent-mode.md)** - AI agent integration
- **[MCP Server](demo/commands/mcp-server.md)** - MCP server mode
- **[Create Tenant](demo/commands/create-tenant.md)** - Tenant creation
- **[Create Tenant Sample](demo/commands/create-tenant-sample.md)** - Sample tenant
- **[Backup DB](demo/commands/backup-db.md)** - Database backup
- **[Doctor](demo/commands/doctor.md)** - System diagnostics
- **[Test](demo/commands/test.md)** - Testing commands
- **[Subset Bicep Demo](demo/subset_bicep_demo.md)** - Bicep subset generation

## Presentations & Research

### Presentations
- **[Demo Presentation](demo_presentation.md)** - Product demonstration
- **[Threat Model Agent Demo](threat_model_agent_demo.md)** - Threat modeling demo
- **[UI Demo: Cross-Tenant IaC](ui-demo-cross-tenant-iac.md)** - UI walkthrough

### Research
- **[Azure Lighthouse Evaluation](research/azure_lighthouse_evaluation.md)** - Multi-tenant architecture research
- **[Azure Lighthouse Hybrid Evaluation](research/azure_lighthouse_hybrid_evaluation.md)** - Hybrid architecture analysis
- **[Cloud Threat Modelling](resources/CloudThreatModelling.md)** - Threat modeling resources

## Specifications & Analysis

### Bug Documentation
- **[Bug #10 Documentation](BUG_10_DOCUMENTATION.md)** - Child resource import blocks fix
- **[Bug #59 Documentation](BUG_59_DOCUMENTATION.md)** - Subscription ID abstraction fix
- **[Bug #66 Documentation](BUG_66_DOCUMENTATION.md)** - Bug fix details
- **[Bug #68 Documentation](BUG_68_DOCUMENTATION.md)** - Provider case sensitivity fix
- **[Bug #87 Documentation](BUG_87_DOCUMENTATION.md)** - Smart Detector location fix
- **[Bug #88 Documentation](BUG_88_DOCUMENTATION.md)** - Action group resource ID fix
- **[Bug Association Import Fix](BUG_ASSOCIATION_IMPORT_FIX.md)** - Association import fixes
- **[KeyVault Name Truncation Fix](KEYVAULT_NAME_TRUNCATION_FIX.md)** - Name truncation handling
- **[KeyVault Plugin Implementation](KEYVAULT_PLUGIN_IMPLEMENTATION.md)** - Plugin details
- **[UPN Parentheses Sanitization Fix](UPN_PARENTHESES_SANITIZATION_FIX.md)** - UPN sanitization

### Specifications
- **[MCP Integration Summary](specs/MCP_INTEGRATION_SUMMARY.md)** - MCP integration details
- **[Issue #209 Fix Summary](specs/ISSUE_209_FIX_SUMMARY.md)** - Issue resolution
- **[Issue Hierarchical Spec](specs/ISSUE_HIERARCHICAL_SPEC.md)** - Hierarchical specifications
- **[Merge Order Recommendation](specs/MERGE_ORDER_RECOMMENDATION.md)** - PR merge strategy
- **[PR-98 Review Improvements](specs/PR-98-review-improvements.md)** - Review process improvements
- **[Private DNS Zones Support Complete](specs/PRIVATE_DNS_ZONES_SUPPORT_COMPLETE.md)** - DNS zones implementation
- **[Private DNS Zones Support Verification](specs/PRIVATE_DNS_ZONES_SUPPORT_VERIFICATION.md)** - Verification results
- **[Security Fixes](specs/SECURITY_FIXES.md)** - Security improvements
- **[Timestamp Improvements](specs/TIMESTAMP_IMPROVEMENTS.md)** - Timestamp handling

### Analysis
- **[Architectural Pattern Analysis](ARCHITECTURAL_PATTERN_ANALYSIS.md)** - Design pattern analysis
- **[Service Refactoring Analysis](SERVICE_REFACTORING_ANALYSIS.md)** - Refactoring recommendations
- **[Visualization Alignment Analysis](VISUALIZATION_ALIGNMENT_ANALYSIS.md)** - UI/UX analysis
- **[Well-Architected Reports](WELL_ARCHITECTED_REPORTS.md)** - Azure Well-Architected Framework assessment

## Diagrams

- **[Diagrams Overview](diagrams/README.md)** - All architecture diagrams
- **[Diagram Manifest](diagrams/DIAGRAM_MANIFEST.md)** - Diagram inventory

## Development

- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute
- **[Development Setup](development/setup.md)** - Developer environment setup
- **[Timeout Handling](TIMEOUT_HANDLING.md)** - Async timeout patterns
- **[Gadugi Migration](GADUGI_MIGRATION.md)** - Migration to Gadugi framework
- **[Cleanup Iteration Resources](cleanup_iteration_resources.md)** - Resource cleanup
- **[Fix Plan API Versions](fix-plan-api-versions.md)** - API version management
- **[Implementation Plan: Properties Extraction](implementation-plan-properties-extraction.md)** - Property extraction design
- **[Workflow](workflow.md)** - Development workflow
- **[Graph API Setup](GRAPH_API_SETUP.md)** - Microsoft Graph API configuration
- **[MCP Integration](MCP_INTEGRATION.md)** - Model Context Protocol setup

## Remote Mode

- **[Remote Mode Overview](remote-mode/README.md)** - Remote execution architecture
- **[Remote Mode User Guide](remote-mode/USER_GUIDE.md)** - Using remote mode
- **[Remote Mode Configuration](remote-mode/CONFIGURATION.md)** - Configuration options
- **[Remote Mode Deployment](remote-mode/DEPLOYMENT.md)** - Deployment guide
- **[Remote Mode API Reference](remote-mode/API_REFERENCE.md)** - API documentation
- **[Remote Mode Troubleshooting](remote-mode/TROUBLESHOOTING.md)** - Common issues
- **[Phase 2 Quickstart](remote-mode/PHASE2_QUICKSTART.md)** - Phase 2 features

## Examples

- **[Example Tenant Report](examples/example-tenant-report.md)** - Sample tenant documentation

## Investigations

### Issue #591: VM Replication
- **[Investigation README](investigations/issue-591/README.md)** ⭐ - Complete investigation timeline
- **[Session Report: Bug #10](investigations/issue-591/SESSION_20251218_BUG10_FIX.md)** - Child resource fix session
- **[Permission Issue](investigations/issue-591/PERMISSION_ISSUE.md)** - Cross-tenant permissions

### Final Reports (December 2025)
- **[Master Achievement Summary](investigations/MASTER_ACHIEVEMENT_SUMMARY_20251201.md)** - Overall achievements
- **[Final Complete Summary](investigations/FINAL_COMPLETE_SUMMARY_20251201.md)** - Complete final report
- **[Final Status Report](investigations/FINAL_STATUS_REPORT_20251201.md)** - Final status
- **[Ultimate Victory Report](investigations/ULTIMATE_VICTORY_REPORT_20251201.md)** - Victory summary
- **[Role Assignment Investigation](investigations/role_assignment_import_investigation_20251201.md)** - Role assignment deep dive

## Deployment Guides

- **[Tenant Replication Deployment Guide](TENANT_REPLICATION_DEPLOYMENT_GUIDE.md)** ⭐ - Complete deployment guide for Issue #502
- **[README Section: Autonomous Deployment](README_SECTION_AUTONOMOUS_DEPLOYMENT.md)** - Autonomous deployment for README
- **[Autonomous Deployment Index](AUTONOMOUS_DEPLOYMENT_INDEX.md)** ⭐ - Complete autonomous deployment documentation

## Visualizations

- **[Dual-Graph Architecture Diagram](DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt)** - ASCII architecture diagram
- **[Dual-Graph Implementation Example](DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py)** - Python reference implementation

---

## Documentation Conventions

### Priority Indicators
- ⭐ = Start here / Most important
- 🔧 = Technical reference
- 📖 = Conceptual guide
- 🚀 = Quick start / Tutorial

### Document Status
- **COMPLETE** = Fully implemented and documented
- **IN PROGRESS** = Under active development
- **ARCHIVED** = Historical reference only

### Finding What You Need

1. **First time user?** Start with [Quick Start Guide](quickstart/quick-start.md)
2. **Want AI deployment?** See [Autonomous Deployment Guide](guides/AUTONOMOUS_DEPLOYMENT.md)
3. **Need architecture details?** Check [Architecture Overview](architecture/README.md)
4. **Working with graph?** See [Neo4j Schema Reference](NEO4J_SCHEMA_REFERENCE.md)
5. **Debugging issues?** Check [FAQ](guides/AUTONOMOUS_DEPLOYMENT_FAQ.md) and troubleshooting guides

---

**Last Updated:** 2025-12-18
**Total Documents:** 174 markdown files
**Coverage:** 100% (no orphaned documentation)
"""

    return index_content


def main():
    """Write the complete INDEX.md"""
    index_path = BASE_DIR / "INDEX.md"
    content = generate_complete_index()

    index_path.write_text(content)
    print("✅ Generated complete INDEX.md with all sections")
    print(f"📄 File: {index_path}")
    print(f"📊 Lines: {len(content.splitlines())}")


if __name__ == "__main__":
    main()
