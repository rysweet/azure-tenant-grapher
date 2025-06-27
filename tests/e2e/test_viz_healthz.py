import pytest
from fastapi.testclient import TestClient
from src.visualization.server import create_app

@pytest.mark.e2e
def test_healthz_works():
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}