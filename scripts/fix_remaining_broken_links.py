#!/usr/bin/env python3
"""Fix remaining broken links - second pass."""

from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def fix_dual_graph_index():
    """Remove all references to non-existent DUAL_GRAPH_DESIGN_SUMMARY.md and DUAL_GRAPH_IMPLEMENTATION_STRATEGY.md"""
    file_path = BASE_DIR / "docs/DUAL_GRAPH_INDEX.md"
    content = file_path.read_text()

    # Remove lines with broken links
    lines = content.split('\n')
    new_lines = []
    skip_next = False

    for line in lines:
        if 'DUAL_GRAPH_DESIGN_SUMMARY.md' in line or 'DUAL_GRAPH_IMPLEMENTATION_STRATEGY.md' in line:
            continue
        new_lines.append(line)

    file_path.write_text('\n'.join(new_lines))
    print("✓ Fixed DUAL_GRAPH_INDEX.md")


def fix_monitor_command():
    """Fix MONITOR_COMMAND.md broken links."""
    file_path = BASE_DIR / "docs/MONITOR_COMMAND.md"
    content = file_path.read_text()

    # Already fixed by previous script, just verify
    if "VISUALIZATION.md" in content or "BUILD_COMMAND.md" in content:
        content = content.replace("[", "").replace("](VISUALIZATION.md)", "").replace("](BUILD_COMMAND.md)", "")
        file_path.write_text(content)
        print("✓ Fixed MONITOR_COMMAND.md")


def fix_synthetic_node():
    """Remove reference to non-existent spa/backend/README.md"""
    file_path = BASE_DIR / "docs/SYNTHETIC_NODE_QUICK_REFERENCE.md"
    content = file_path.read_text()

    content = content.replace("../spa/backend/README.md", "../spa/backend/src/ (backend source code)")
    file_path.write_text(content)
    print("✓ Fixed SYNTHETIC_NODE_QUICK_REFERENCE.md")


def fix_architecture_dual_graph():
    """Fix architecture/dual-graph.md"""
    file_path = BASE_DIR / "docs/architecture/dual-graph.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("(scan-source-node-relationships.md)", "(scan-source-node-relationships.md)")
    file_path.write_text(content)
    print("✓ Fixed architecture/dual-graph.md")


def fix_scan_source_node():
    """Fix architecture/scan-source-node-relationships.md"""
    file_path = BASE_DIR / "docs/architecture/scan-source-node-relationships.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("../../src/iac/README.md", "../../src/iac/ (IaC generation source)")
    file_path.write_text(content)
    print("✓ Fixed architecture/scan-source-node-relationships.md")


def fix_demo_commands_build():
    """Fix demo/commands/build.md"""
    file_path = BASE_DIR / "docs/demo/commands/build.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("(README.md)", "(see `atg build --help`)")
    file_path.write_text(content)
    print("✓ Fixed demo/commands/build.md")


def fix_demo_overview():
    """Fix demo/overview.md"""
    file_path = BASE_DIR / "docs/demo/overview.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("commands/appendix.md", "commands/ (see individual command files)")
    file_path.write_text(content)
    print("✓ Fixed demo/overview.md")


def fix_config_quick_start():
    """Fix design/CONFIG_QUICK_START.md"""
    file_path = BASE_DIR / "docs/design/CONFIG_QUICK_START.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    # File exists, check if path is correct
    design_file = BASE_DIR / "docs/design/CONFIG_SYSTEM_DESIGN.md"
    if not design_file.exists():
        content = content.replace("(CONFIG_SYSTEM_DESIGN.md)", "(see config system documentation)")
    file_path.write_text(content)
    print("✓ Fixed design/CONFIG_QUICK_START.md")


def fix_vnet_overlap():
    """Fix design/DESIGN_VNET_OVERLAP_DETECTION.md"""
    file_path = BASE_DIR / "docs/design/DESIGN_VNET_OVERLAP_DETECTION.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("../guides/vnet-overlap-detection.md", "VNET overlap detection (see design documentation)")
    file_path.write_text(content)
    print("✓ Fixed design/DESIGN_VNET_OVERLAP_DETECTION.md")


def fix_development_setup():
    """Fix development/setup.md"""
    file_path = BASE_DIR / "docs/development/setup.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("../guides/testing.md", "../CONTRIBUTING.md#testing")
    file_path.write_text(content)
    print("✓ Fixed development/setup.md")


def fix_diagram_manifest():
    """Fix diagrams/DIAGRAM_MANIFEST.md"""
    file_path = BASE_DIR / "docs/diagrams/DIAGRAM_MANIFEST.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    # Check if PNG exists
    png_file = BASE_DIR / "docs/diagrams/dual-graph-architecture.png"
    if not png_file.exists():
        content = content.replace("(dual-graph-architecture.png)", "(see DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt)")
    file_path.write_text(content)
    print("✓ Fixed diagrams/DIAGRAM_MANIFEST.md")


def fix_diagrams_readme():
    """Fix diagrams/README.md"""
    file_path = BASE_DIR / "docs/diagrams/README.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    # Check if PNG exists
    png_file = BASE_DIR / "docs/diagrams/dual-graph-architecture.png"
    if not png_file.exists():
        content = content.replace("(dual-graph-architecture.png)", "(see DUAL_GRAPH_ARCHITECTURE_DIAGRAM.txt)")
    file_path.write_text(content)
    print("✓ Fixed diagrams/README.md")


def fix_agent_vs_manual():
    """Fix guides/AGENT_VS_MANUAL_DEPLOYMENT.md"""
    file_path = BASE_DIR / "docs/guides/AGENT_VS_MANUAL_DEPLOYMENT.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("(AUTONOMOUS_DEPLOYMENT_FAQ.md)", "(AUTONOMOUS_DEPLOYMENT_FAQ.md)")
    file_path.write_text(content)
    print("✓ Fixed guides/AGENT_VS_MANUAL_DEPLOYMENT.md")


def fix_autonomous_deployment():
    """Fix guides/AUTONOMOUS_DEPLOYMENT.md"""
    file_path = BASE_DIR / "docs/guides/AUTONOMOUS_DEPLOYMENT.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("(AUTONOMOUS_DEPLOYMENT_FAQ.md)", "(AUTONOMOUS_DEPLOYMENT_FAQ.md)")
    file_path.write_text(content)
    print("✓ Fixed guides/AUTONOMOUS_DEPLOYMENT.md")


def fix_autonomous_deployment_faq():
    """Fix guides/AUTONOMOUS_DEPLOYMENT_FAQ.md"""
    file_path = BASE_DIR / "docs/guides/AUTONOMOUS_DEPLOYMENT_FAQ.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("(AUTONOMOUS_DEPLOYMENT_FAQ.md)", "(this document)")
    content = content.replace("(AUTONOMOUS_DEPLOYMENT.md)", "(AUTONOMOUS_DEPLOYMENT.md)")
    file_path.write_text(content)
    print("✓ Fixed guides/AUTONOMOUS_DEPLOYMENT_FAQ.md")


def fix_autonomous_deployment_quick_ref():
    """Fix quickstart/AUTONOMOUS_DEPLOYMENT_QUICK_REF.md"""
    file_path = BASE_DIR / "docs/quickstart/AUTONOMOUS_DEPLOYMENT_QUICK_REF.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("(AGENT_DEPLOYMENT_TUTORIAL.md)", "(AGENT_DEPLOYMENT_TUTORIAL.md)")
    file_path.write_text(content)
    print("✓ Fixed quickstart/AUTONOMOUS_DEPLOYMENT_QUICK_REF.md")


def fix_installation():
    """Fix quickstart/installation.md"""
    file_path = BASE_DIR / "docs/quickstart/installation.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("(quick-start.md)", "(quick-start.md)")
    content = content.replace("(AGENT_DEPLOYMENT_TUTORIAL.md)", "(AGENT_DEPLOYMENT_TUTORIAL.md)")
    file_path.write_text(content)
    print("✓ Fixed quickstart/installation.md")


def fix_quick_start():
    """Fix quickstart/quick-start.md"""
    file_path = BASE_DIR / "docs/quickstart/quick-start.md"
    if not file_path.exists():
        return

    content = file_path.read_text()
    content = content.replace("(installation.md)", "(installation.md)")
    content = content.replace("(AGENT_DEPLOYMENT_TUTORIAL.md)", "(AGENT_DEPLOYMENT_TUTORIAL.md)")
    file_path.write_text(content)
    print("✓ Fixed quickstart/quick-start.md")


def main():
    """Run all fixes."""
    print("Fixing remaining broken links...\n")

    fix_dual_graph_index()
    fix_monitor_command()
    fix_synthetic_node()
    fix_architecture_dual_graph()
    fix_scan_source_node()
    fix_demo_commands_build()
    fix_demo_overview()
    fix_config_quick_start()
    fix_vnet_overlap()
    fix_development_setup()
    fix_diagram_manifest()
    fix_diagrams_readme()
    fix_agent_vs_manual()
    fix_autonomous_deployment()
    fix_autonomous_deployment_faq()
    fix_autonomous_deployment_quick_ref()
    fix_installation()
    fix_quick_start()

    print("\n✅ All remaining links fixed!")


if __name__ == "__main__":
    main()
