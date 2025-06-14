import glob
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict

from src.graph_visualizer import GraphVisualizer


def test_spec_link_appears_in_html(monkeypatch: Any) -> None:
    # Setup: create dummy spec file in ./specs/
    tmpdir = tempfile.mkdtemp()
    specs_dir = os.path.join(tmpdir, "specs")
    os.makedirs(specs_dir, exist_ok=True)
    spec_path = os.path.join(specs_dir, "20240101_120000_tenant_spec.md")
    with open(spec_path, "w") as f:
        f.write("# Dummy spec")

    # Patch os.getcwd to tmpdir so GraphVisualizer looks in our temp specs/
    monkeypatch.setattr(os, "getcwd", lambda: tmpdir)

    # Minimal graph data for HTML
    class DummyGV(GraphVisualizer):
        def extract_graph_data(self, link_to_hierarchy: bool = False) -> Dict[str, Any]:
            return {
                "nodes": [],
                "links": [],
                "node_types": [],
                "relationship_types": [],
            }

    gv = DummyGV("bolt://localhost:7687", "neo4j", "password")
    # Use the public method instead of the protected one
    output_path = os.path.join(tmpdir, "test.html")
    gv.generate_html_visualization(output_path=output_path, specification_path=None)

    # Read the generated HTML file
    with open(output_path, encoding="utf-8") as f:
        html = f.read()

    # Assert the spec link is present
    assert "View Tenant Specification" in html
    assert "20240101_120000_tenant_spec.md" in html


def test_cli_visualize_link_hierarchy(tmp_path: Any) -> None:
    """Trivial: run CLI with --link-hierarchy and assert HTML file is created."""
    # Skip if Neo4j is not running (avoid test failure in CI)
    import socket

    s = socket.socket()
    try:
        s.settimeout(1)
        s.connect(("localhost", 7687))  # Fix: use standard Neo4j port 7687, not 7688
    except Exception:
        import pytest

        pytest.skip("Neo4j not running on localhost:7687")
    finally:
        s.close()

    # Remove any pre-existing output files
    for f in glob.glob("azure_graph_visualization_*.html"):
        os.remove(f)

    # Run the CLI visualize command
    result = subprocess.run(
        ["uv", "run", "python", "scripts/cli.py", "visualize", "--link-hierarchy"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Should not error
    assert result.returncode == 0

    # Check that an HTML file was created
    html_files = glob.glob("azure_graph_visualization_*.html")
    assert html_files, "No visualization HTML file created"
    # Clean up
    for f in html_files:
        os.remove(f)
    # Remove the temp directory created by tmp_path fixture
    if "tmp_path" in locals():
        shutil.rmtree(str(tmp_path))
