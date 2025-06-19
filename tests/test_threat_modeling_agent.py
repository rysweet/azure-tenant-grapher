import os
from pathlib import Path
from typing import Any, Dict

import pytest

from src.threat_modeling_agent.asb_mapper import map_controls
from src.threat_modeling_agent.dfd_builder import DFDBuilderStrategy
from src.threat_modeling_agent.report_builder import build_markdown
from src.threat_modeling_agent.threat_enumerator import enumerate_threats
from src.threat_modeling_agent.tmt_runner import run_tmt


@pytest.fixture
def mock_graph_data():
    return {
        "nodes": [
            {"id": "user1", "label": "User", "type": "External Interactor"},
            {"id": "app1", "label": "App Service", "type": "Process"},
            {"id": "db1", "label": "SQL DB", "type": "Data Store"},
        ],
        "edges": [
            {"source": "user1", "target": "app1", "label": "HTTPS"},
            {"source": "app1", "target": "db1", "label": "TCP 1433"},
        ],
    }


def test_dfd_builder_mermaid(mock_graph_data: Dict[str, Any]) -> None:
    mermaid = DFDBuilderStrategy.run({}, mock_graph_data)[2]
    assert mermaid is not None
    assert "flowchart TD" in mermaid
    assert "user1((User))" in mermaid or 'user1(("User"))' in mermaid
    assert 'app1["App Service"]' in mermaid
    assert 'db1[(("SQL DB"))]' in mermaid
    assert "user1 -->|HTTPS| app1" in mermaid
    assert "app1 -->|TCP 1433| db1" in mermaid


def test_tmt_runner_and_enumerator(
    tmp_path: Path, mock_graph_data: Dict[str, Any]
) -> None:
    # Simulate a .tm7 file for TMT runner
    tm7_path = tmp_path / "model.tm7"
    tm7_path.write_text("stub tm7 content")
    threats = run_tmt(str(tm7_path))
    assert isinstance(threats, list)
    if threats:
        enumerated = enumerate_threats(threats)
        assert isinstance(enumerated, list)
        if enumerated:
            mapped = map_controls(enumerated)
            assert isinstance(mapped, list)
            for threat in mapped:
                assert "asb_controls" in threat


def test_report_builder(tmp_path: Path, mock_graph_data: Dict[str, Any]) -> None:
    # Use stub threats and ASB mapping
    threats = [
        {
            "id": "TMT-001",
            "title": "Data Exposure",
            "description": "Sensitive data may be exposed in transit.",
            "severity": "High",
            "stride": "I",
            "asb_controls": [
                {
                    "control_id": "ASB-DS-4",
                    "title": "Data Confidentiality",
                    "description": "Encrypt sensitive data and restrict access.",
                }
            ],
        }
    ]
    mermaid = DFDBuilderStrategy.run({}, mock_graph_data)[2]
    assert mermaid is not None
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("# Spec")
    report_path = build_markdown(mermaid, threats, str(spec_path))
    assert report_path is not None
    assert os.path.exists(report_path)
    content = open(report_path).read()
    assert "# Threat Modeling Report" in content
    assert "Data Exposure" in content
    assert "ASB-DS-4" in content
