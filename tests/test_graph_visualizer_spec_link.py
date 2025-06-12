import os
import shutil
import tempfile

from src.graph_visualizer import GraphVisualizer


def test_spec_link_appears_in_html(monkeypatch):
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
        def extract_graph_data(self):
            return {
                "nodes": [],
                "links": [],
                "node_types": [],
                "relationship_types": [],
            }

    gv = DummyGV("bolt://localhost:7688", "neo4j", "password")
    html = gv._generate_html_template(gv.extract_graph_data(), specification_path=None)
    # Assert the spec link is present
    assert "View Tenant Specification" in html
    assert "20240101_120000_tenant_spec.md" in html

    shutil.rmtree(tmpdir)
