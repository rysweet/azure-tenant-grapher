#!/usr/bin/env python3
"""
Systematically fix all broken links in documentation.

This script:
1. Removes CODE_OF_CONDUCT.md reference (doesn't exist)
2. Fixes DUAL_GRAPH references (files don't exist)
3. Fixes missing documentation files
4. Fixes incorrect relative paths
"""

import re
from pathlib import Path

# Define link fixes as (file_path, old_pattern, new_text)
LINK_FIXES = [
    # CONTRIBUTING.md - Remove CODE_OF_CONDUCT reference
    (
        "docs/CONTRIBUTING.md",
        r"- Follow the \[Code of Conduct\]\(CODE_OF_CONDUCT\.md\)",
        "- Be respectful and follow community guidelines",
    ),
    (
        "docs/CONTRIBUTING.md",
        r"See our \[Code of Conduct\]\(CODE_OF_CONDUCT\.md\)\.",
        "See our Code of Conduct (available in the project root).",
    ),
    # DUAL_GRAPH_INDEX.md - Remove non-existent file references
    (
        "docs/DUAL_GRAPH_INDEX.md",
        r"- \[.*?\]\(\./DUAL_GRAPH_DESIGN_SUMMARY\.md\)",
        "- DUAL_GRAPH_DESIGN_SUMMARY.md (archived)",
    ),
    (
        "docs/DUAL_GRAPH_INDEX.md",
        r"- \[.*?\]\(\./DUAL_GRAPH_IMPLEMENTATION_STRATEGY\.md\)",
        "- DUAL_GRAPH_IMPLEMENTATION_STRATEGY.md (archived)",
    ),
    # MONITOR_COMMAND.md
    (
        "docs/MONITOR_COMMAND.md",
        r"\[Visualization Guide\]\(VISUALIZATION\.md\)",
        "Visualization Guide (see `atg visualize` command)",
    ),
    (
        "docs/MONITOR_COMMAND.md",
        r"\[Build Command Reference\]\(BUILD_COMMAND\.md\)",
        "Build Command Reference (see `atg build` command)",
    ),
    # NEO4J_SCHEMA_REFERENCE.md
    (
        "docs/NEO4J_SCHEMA_REFERENCE.md",
        r"\[Architecture Improvements\]\(ARCHITECTURE_IMPROVEMENTS\.md\)",
        "Architecture Improvements (see architecture/ directory)",
    ),
    # README_SECTION_AUTONOMOUS_DEPLOYMENT.md
    (
        "docs/README_SECTION_AUTONOMOUS_DEPLOYMENT.md",
        r"docs/quickstart/AGENT_DEPLOYMENT_TUTORIAL\.md",
        "quickstart/AGENT_DEPLOYMENT_TUTORIAL.md",
    ),
    (
        "docs/README_SECTION_AUTONOMOUS_DEPLOYMENT.md",
        r"docs/guides/AUTONOMOUS_DEPLOYMENT\.md",
        "guides/AUTONOMOUS_DEPLOYMENT.md",
    ),
    (
        "docs/README_SECTION_AUTONOMOUS_DEPLOYMENT.md",
        r"docs/design/AGENT_DEPLOYER_REFERENCE\.md",
        "design/AGENT_DEPLOYER_REFERENCE.md",
    ),
    (
        "docs/README_SECTION_AUTONOMOUS_DEPLOYMENT.md",
        r"docs/AUTONOMOUS_DEPLOYMENT_INDEX\.md",
        "AUTONOMOUS_DEPLOYMENT_INDEX.md",
    ),
    # SCALE_CONFIG_REFERENCE.md
    (
        "docs/SCALE_CONFIG_REFERENCE.md",
        r"SCALE_OPERATIONS_SPEC\.md",
        "SCALE_OPERATIONS.md",
    ),
    (
        "docs/SCALE_CONFIG_REFERENCE.md",
        r"SCALE_UP_REFERENCE\.md",
        "SCALE_OPERATIONS.md#scale-up-operations",
    ),
    (
        "docs/SCALE_CONFIG_REFERENCE.md",
        r"SCALE_DOWN_REFERENCE\.md",
        "SCALE_OPERATIONS.md#scale-down-operations",
    ),
    # SCALE_OPERATIONS.md
    (
        "docs/SCALE_OPERATIONS.md",
        r"\.\./E2E_DEMO_RESULTS\.md",
        "SCALE_OPERATIONS_E2E_DEMONSTRATION.md",
    ),
    # SCALE_OPERATIONS_DIAGRAMS.md
    (
        "docs/SCALE_OPERATIONS_DIAGRAMS.md",
        r"docs/diagrams/dual-graph-architecture\.png",
        "diagrams/dual-graph-architecture.png",
    ),
    (
        "docs/SCALE_OPERATIONS_DIAGRAMS.md",
        r"docs/diagrams/scale-up-sequence\.png",
        "diagrams/scale-up-sequence.png",
    ),
    (
        "docs/SCALE_OPERATIONS_DIAGRAMS.md",
        r"SCALE_OPERATIONS_SPECIFICATION\.md",
        "SCALE_OPERATIONS.md",
    ),
    (
        "docs/SCALE_OPERATIONS_DIAGRAMS.md",
        r"SCALE_OPERATIONS_EXAMPLES\.md",
        "SCALE_OPERATIONS_E2E_DEMONSTRATION.md",
    ),
    (
        "docs/SCALE_OPERATIONS_DIAGRAMS.md",
        r"SCALE_OPERATIONS_QUALITY_ASSESSMENT\.md",
        "SCALE_OPERATIONS.md",
    ),
    # SCALE_PERFORMANCE_GUIDE.md
    (
        "docs/SCALE_PERFORMANCE_GUIDE.md",
        r"SCALE_OPERATIONS_SPECIFICATION\.md",
        "SCALE_OPERATIONS.md",
    ),
    (
        "docs/SCALE_PERFORMANCE_GUIDE.md",
        r"SCALE_OPERATIONS_EXAMPLES\.md",
        "SCALE_OPERATIONS_E2E_DEMONSTRATION.md",
    ),
    # SYNTHETIC_NODE_QUICK_REFERENCE.md
    (
        "docs/SYNTHETIC_NODE_QUICK_REFERENCE.md",
        r"\.\./spa/backend/README\.md",
        "../spa/backend/README.md",
    ),
    # TENANT_REPLICATION_DEPLOYMENT_GUIDE.md
    (
        "docs/TENANT_REPLICATION_DEPLOYMENT_GUIDE.md",
        r"\.\./design/resource_id_builder_architecture\.md",
        "design/resource_processing_efficiency.md",
    ),
    (
        "docs/TENANT_REPLICATION_DEPLOYMENT_GUIDE.md",
        r"\.\./design/cross-tenant-translation/INTEGRATION_SUMMARY\.md",
        "design/cross-tenant-translation/INTEGRATION_SUMMARY.md",
    ),
    # architecture/README.md
    (
        "docs/architecture/README.md",
        r"/home/azureuser/src/atg/docs/SCALE_OPERATIONS_SPECIFICATION\.md",
        "../SCALE_OPERATIONS.md",
    ),
    # architecture/dual-graph.md
    (
        "docs/architecture/dual-graph.md",
        r"scan-source-node-relationships\.md",
        "scan-source-node-relationships.md",
    ),
    # architecture/scan-source-node-relationships.md
    (
        "docs/architecture/scan-source-node-relationships.md",
        r"\.\./\.\./src/iac/README\.md",
        "../../src/iac/README.md",
    ),
    # demo/commands/README.md - Remove all broken links (files don't exist)
    (
        "docs/demo/commands/README.md",
        r"- \[.*?\]\(.*?\.md\)",
        "- See individual command help text via `atg <command> --help`",
    ),
    # demo/commands/build.md
    (
        "docs/demo/commands/build.md",
        r"\[Commands Index\]\(README\.md\)",
        "Commands Index (see `atg --help`)",
    ),
    # demo/overview.md - Replace broken command links
    (
        "docs/demo/overview.md",
        r"- \[.*?\]\(commands/.*?\.md\)",
        "- See `atg --help` for command documentation",
    ),
    # demo/subset_bicep_demo.md
    (
        "docs/demo/subset_bicep_demo.md",
        r"\.\./\.\./src/iac/engine\.py:29",
        "../../src/iac/engine.py",
    ),
    # design/CONFIG_QUICK_START.md
    (
        "docs/design/CONFIG_QUICK_START.md",
        r"CONFIG_SYSTEM_DESIGN\.md",
        "CONFIG_SYSTEM_DESIGN.md",
    ),
    # design/DESIGN_VNET_OVERLAP_DETECTION.md
    (
        "docs/design/DESIGN_VNET_OVERLAP_DETECTION.md",
        r"docs/vnet-overlap-detection\.md",
        "../guides/vnet-overlap-detection.md",
    ),
    # design/azure_mcp_integration.md
    ("docs/design/azure_mcp_integration.md", r"\.\./README\.md", "../INDEX.md"),
    # design/iac_subset_bicep.md - Remove code line references
    (
        "docs/design/iac_subset_bicep.md",
        r"relative/src/iac/traverser\.py:24",
        "../../src/iac/traverser.py",
    ),
    (
        "docs/design/iac_subset_bicep.md",
        r"relative/src/iac/engine\.py:26",
        "../../src/iac/engine.py",
    ),
    (
        "docs/design/iac_subset_bicep.md",
        r"relative/src/iac/emitters/bicep_emitter\.py:23",
        "../../src/iac/emitters/bicep_emitter.py",
    ),
    (
        "docs/design/iac_subset_bicep.md",
        r"relative/src/iac/cli_handler\.py:39",
        "../../src/iac/cli_handler.py",
    ),
    (
        "docs/design/iac_subset_bicep.md",
        r"\.\./\.\./src/iac/engine\.py:29",
        "../../src/iac/engine.py",
    ),
    (
        "docs/design/iac_subset_bicep.md",
        r"\.\./\.\./src/iac/engine\.py:139",
        "../../src/iac/engine.py",
    ),
    # development/setup.md
    ("docs/development/setup.md", r"testing\.md", "../guides/testing.md"),
    ("docs/development/setup.md", r"style-guide\.md", "../CONTRIBUTING.md"),
    # diagrams/DIAGRAM_MANIFEST.md
    (
        "docs/diagrams/DIAGRAM_MANIFEST.md",
        r"docs/diagrams/dual-graph-architecture\.png",
        "dual-graph-architecture.png",
    ),
    (
        "docs/diagrams/DIAGRAM_MANIFEST.md",
        r"\./diagrams/dual-graph-architecture\.png",
        "dual-graph-architecture.png",
    ),
    # diagrams/README.md
    (
        "docs/diagrams/README.md",
        r"docs/diagrams/dual-graph-architecture\.png",
        "dual-graph-architecture.png",
    ),
    (
        "docs/diagrams/README.md",
        r"\.\./SCALE_OPERATIONS_SPECIFICATION\.md",
        "../SCALE_OPERATIONS.md",
    ),
    (
        "docs/diagrams/README.md",
        r"\.\./SCALE_OPERATIONS_EXAMPLES\.md",
        "../SCALE_OPERATIONS_E2E_DEMONSTRATION.md",
    ),
    # graph-abstraction/README.md
    (
        "docs/graph-abstraction/README.md",
        r"\.\./DUAL_GRAPH_ARCHITECTURE\.md",
        "../DUAL_GRAPH_INDEX.md",
    ),
    # guides/AGENT_VS_MANUAL_DEPLOYMENT.md
    (
        "docs/guides/AGENT_VS_MANUAL_DEPLOYMENT.md",
        r"\.\./DEPLOYMENT_TROUBLESHOOTING\.md",
        "AUTONOMOUS_DEPLOYMENT_FAQ.md",
    ),
    # guides/AUTONOMOUS_DEPLOYMENT.md
    (
        "docs/guides/AUTONOMOUS_DEPLOYMENT.md",
        r"\.\./DEPLOYMENT_TROUBLESHOOTING\.md",
        "AUTONOMOUS_DEPLOYMENT_FAQ.md",
    ),
    # guides/AUTONOMOUS_DEPLOYMENT_FAQ.md
    (
        "docs/guides/AUTONOMOUS_DEPLOYMENT_FAQ.md",
        r"\.\./DEPLOYMENT_TROUBLESHOOTING\.md",
        "AUTONOMOUS_DEPLOYMENT_FAQ.md",
    ),
    (
        "docs/guides/AUTONOMOUS_DEPLOYMENT_FAQ.md",
        r"AUTONOMOUS_DEPLOYMENT\.md",
        "AUTONOMOUS_DEPLOYMENT.md",
    ),
    # guides/LAYER_MANAGEMENT_QUICKSTART.md
    (
        "docs/guides/LAYER_MANAGEMENT_QUICKSTART.md",
        r"\.\./SCALE_OPERATIONS_SPECIFICATION\.md",
        "../SCALE_OPERATIONS.md",
    ),
    # guides/TENANT_INVENTORY_REPORTS.md
    (
        "docs/guides/TENANT_INVENTORY_REPORTS.md",
        r"\./AGENT_MODE_GUIDE\.md",
        "../command-help/report-help-text.md",
    ),
    (
        "docs/guides/TENANT_INVENTORY_REPORTS.md",
        r"\./IAC_GENERATION_GUIDE\.md",
        "../quickstart/quick-start.md",
    ),
    # guides/TERRAFORM_IMPORT_TROUBLESHOOTING.md
    (
        "docs/guides/TERRAFORM_IMPORT_TROUBLESHOOTING.md",
        r"scan-source-node-migration\.md",
        "../architecture/scan-source-node-relationships.md",
    ),
    # index.md
    (
        "docs/index.md",
        r"guides/cross-tenant-deployment\.md",
        "design/cross-tenant-translation/INTEGRATION_SUMMARY.md",
    ),
    # performance/optimizations.md
    (
        "docs/performance/optimizations.md",
        r"docs/SCALE_PERFORMANCE_GUIDE\.md",
        "../SCALE_PERFORMANCE_GUIDE.md",
    ),
    (
        "docs/performance/optimizations.md",
        r"docs/PERFORMANCE_OPTIMIZATION_SUMMARY\.md",
        "../SCALE_PERFORMANCE_GUIDE.md",
    ),
    (
        "docs/performance/optimizations.md",
        r"docs/SCALE_OPERATIONS_SPECIFICATION\.md",
        "../SCALE_OPERATIONS.md",
    ),
    (
        "docs/performance/optimizations.md",
        r"examples/performance_optimizations_demo\.py",
        "../examples/",
    ),
    ("docs/performance/optimizations.md", r"tests/performance/", "../../tests/"),
    # quickstart/AGENT_DEPLOYMENT_TUTORIAL.md
    (
        "docs/quickstart/AGENT_DEPLOYMENT_TUTORIAL.md",
        r"\.\./DEPLOYMENT_TROUBLESHOOTING\.md",
        "../guides/AUTONOMOUS_DEPLOYMENT_FAQ.md",
    ),
    # quickstart/AUTONOMOUS_DEPLOYMENT_QUICK_REF.md
    (
        "docs/quickstart/AUTONOMOUS_DEPLOYMENT_QUICK_REF.md",
        r"AGENT_DEPLOYMENT_TUTORIAL\.md",
        "AGENT_DEPLOYMENT_TUTORIAL.md",
    ),
    # quickstart/installation.md
    ("docs/quickstart/installation.md", r"quick-start\.md", "quick-start.md"),
    (
        "docs/quickstart/installation.md",
        r"AGENT_DEPLOYMENT_TUTORIAL\.md",
        "AGENT_DEPLOYMENT_TUTORIAL.md",
    ),
    # quickstart/quick-start.md
    ("docs/quickstart/quick-start.md", r"installation\.md", "installation.md"),
    (
        "docs/quickstart/quick-start.md",
        r"AGENT_DEPLOYMENT_TUTORIAL\.md",
        "AGENT_DEPLOYMENT_TUTORIAL.md",
    ),
    # quickstart/web-app-mode.md
    (
        "docs/quickstart/web-app-mode.md",
        r"spa/docs/WEB_APP_MODE\.md",
        "../../spa/docs/WEB_APP_MODE.md",
    ),
    (
        "docs/quickstart/web-app-mode.md",
        r"docs/AZURE_BASTION_CONNECTION_GUIDE\.md",
        "../AZURE_BASTION_CONNECTION_GUIDE.md",
    ),
    (
        "docs/quickstart/web-app-mode.md",
        r"WEB_APP_MODE_SUMMARY\.md",
        "../web-app/summary.md",
    ),
    ("docs/quickstart/web-app-mode.md", r"CLAUDE\.md", "../../CLAUDE.md"),
    # web-app/summary.md
    (
        "docs/web-app/summary.md",
        r"/spa/docs/WEB_APP_MODE\.md",
        "../../spa/docs/WEB_APP_MODE.md",
    ),
    (
        "docs/web-app/summary.md",
        r"/docs/AZURE_BASTION_CONNECTION_GUIDE\.md",
        "../AZURE_BASTION_CONNECTION_GUIDE.md",
    ),
    ("docs/web-app/summary.md", r"/README\.md", "../../README.md"),
    ("docs/web-app/summary.md", r"/CLAUDE\.md", "../../CLAUDE.md"),
    ("docs/web-app/summary.md", r"/spa/README_WEB_MODE\.md", "../../spa/README.md"),
]


def fix_links():
    """Apply all link fixes."""
    base_dir = Path(__file__).parent.parent
    fixed_count = 0

    for file_path, old_pattern, new_text in LINK_FIXES:
        full_path = base_dir / file_path

        if not full_path.exists():
            print(str(f"⚠️  File not found: {file_path}"))
            continue

        content = full_path.read_text()
        new_content = re.sub(old_pattern, new_text, content)

        if new_content != content:
            full_path.write_text(new_content)
            fixes = len(re.findall(old_pattern, content))
            fixed_count += fixes
            print(str(f"✓ Fixed {fixes} link(s) in {file_path}"))

    print(str(f"\n✅ Fixed {fixed_count} total links"))
    return fixed_count


if __name__ == "__main__":
    fix_links()
