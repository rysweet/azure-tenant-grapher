import pytest
import subprocess
import sys
import time
import requests

from src.container_manager import Neo4jContainerManager

@pytest.fixture(scope="session", autouse=True)
def ensure_neo4j():
    manager = Neo4jContainerManager()
    if not manager.setup_neo4j():
        pytest.skip("Neo4j could not be started for test.")

@pytest.mark.e2e
def test_api_graph_endpoint(ensure_neo4j):
    port = 54324
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "src.visualization.server:create_app",
            "--factory",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
            "--lifespan", "on"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        url = f"http://127.0.0.1:{port}/api/graph"
        for i in range(60):
            if proc.poll() is not None:
                out, _ = proc.communicate(timeout=2)
                print(f"Uvicorn process exited early:\n{out}")
                raise RuntimeError("Uvicorn process exited before readiness.")
            try:
                resp = requests.get(url, timeout=0.5)
                if resp.status_code == 200 and "nodes" in resp.json():
                    break
            except Exception:
                pass
            time.sleep(0.1)
        else:
            proc.terminate()
            out, _ = proc.communicate(timeout=2)
            print(f"Uvicorn process output:\n{out}")
            raise TimeoutError("/api/graph endpoint did not become ready in time")
        # Success
        r = requests.get(url)
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data
        assert "links" in data
        assert "node_types" in data
        assert "relationship_types" in data
    finally:
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=2)
            print(f"Uvicorn process output:\n{out}")
        except Exception:
            pass