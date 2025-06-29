import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../iac_out"))
)
import graph_helper


@pytest.fixture
def sample_aad_objects():
    return {
        "users": [{"id": "user1", "displayName": "User One"}],
        "groups": [{"id": "group1", "displayName": "Group One"}],
        "service_principals": [{"id": "sp1", "displayName": "SP One"}],
    }


def test_load_data_json(tmp_path, sample_aad_objects):
    file = tmp_path / "aad_objects.json"
    file.write_text(json.dumps(sample_aad_objects))
    data = graph_helper.load_data(str(file))
    assert data == sample_aad_objects


def test_load_data_yaml(tmp_path, sample_aad_objects):
    file = tmp_path / "aad_objects.yaml"
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed")
    file.write_text(yaml.dump(sample_aad_objects))
    data = graph_helper.load_data(str(file))
    assert data == sample_aad_objects


@patch("graph_helper.GraphClient")
@patch("graph_helper.ClientSecretCredential")
def test_create_aad_objects_idempotent(
    mock_cred, mock_graph, tmp_path, sample_aad_objects, monkeypatch
):
    file = tmp_path / "aad_objects.json"
    file.write_text(json.dumps(sample_aad_objects))
    client = MagicMock()
    # Simulate user exists, group does not, sp does not
    client.get.side_effect = [
        MagicMock(status_code=200),  # user exists
        MagicMock(status_code=404),  # group not found
        MagicMock(status_code=404),  # sp not found
    ]
    client.post.side_effect = [
        MagicMock(status_code=201, json=lambda: {"id": "group1"}),
        MagicMock(status_code=201, json=lambda: {"id": "sp1"}),
    ]
    mock_graph.return_value = client
    monkeypatch.setenv("TENANT_ID", "tid")
    monkeypatch.setenv("CLIENT_ID", "cid")
    monkeypatch.setenv("CLIENT_SECRET", "csecret")
    with patch("builtins.input", return_value="y"):
        graph_helper.create_aad_objects(str(file))
    assert client.post.call_count == 2  # Only group and sp created


@patch("graph_helper.GraphClient")
@patch("graph_helper.ClientSecretCredential")
def test_delete_aad_objects_idempotent(
    mock_cred, mock_graph, tmp_path, sample_aad_objects, monkeypatch
):
    file = tmp_path / "aad_objects.json"
    file.write_text(json.dumps(sample_aad_objects))
    client = MagicMock()
    client.delete.return_value = MagicMock(status_code=204)
    mock_graph.return_value = client
    monkeypatch.setenv("TENANT_ID", "tid")
    monkeypatch.setenv("CLIENT_ID", "cid")
    monkeypatch.setenv("CLIENT_SECRET", "csecret")
    with patch("builtins.input", return_value="y"):
        graph_helper.delete_aad_objects(str(file))
    assert client.delete.call_count == 3


def test_confirm_action_yes(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert graph_helper.confirm_action("create", 1) is True


def test_confirm_action_no(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert graph_helper.confirm_action("delete", 1) is False
