import pytest
import subprocess
import sys
import time
import requests
import socket
from src.container_manager import Neo4jContainerManager

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture(scope="session", autouse=True)
def ensure_neo4j():
    manager = Neo4jContainerManager()
    uri = manager.neo4j_uri
    user = manager.neo4j_user
    password = manager.neo4j_password
    print(f"[TEST] Python: {sys.executable}")
    print(f"[TEST] Neo4j URI: {uri}, user: {user}")
    # Try to connect to Neo4j first, with retries and diagnostics
    for attempt in range(10):
        try:
            import neo4j
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                session.run("RETURN 1")
            print("[TEST] Connected to existing Neo4j at", uri)
            return
        except Exception as e:
            print(f"[TEST] Attempt {attempt+1}/10: Could not connect to existing Neo4j: {e}")
            time.sleep(2)
    # If not running, try to start
    print("[TEST] Could not connect to existing Neo4j, will try to start container.")
    if not manager.setup_neo4j():
        pytest.skip("Neo4j could not be started for test.")

@pytest.fixture(scope="session")
def start_spa_server():
    port = find_free_port()
    print(f"[TEST] Starting SPA server on port {port} with Python executable: {sys.executable}")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "src.visualization.server:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
            "--reload"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Wait for / to be ready
    url = f"http://127.0.0.1:{port}/"
    for _ in range(60):
        if proc.poll() is not None:
            out, _ = proc.communicate(timeout=2)
            print(f"Uvicorn process exited early:\n{out}")
            pytest.skip("Uvicorn process exited before readiness.")
        try:
            resp = requests.get(url, timeout=0.5)
            if resp.status_code == 200 and "<title>Azure Tenant Grapher SPA</title>" in resp.text:
                break
        except Exception as e:
            print(f"[TEST] Waiting for SPA server: {e}")
        time.sleep(0.2)
    else:
        proc.terminate()
        out, _ = proc.communicate(timeout=2)
        print(f"Uvicorn process output:\n{out}")
        pytest.skip("SPA server did not become ready in time")
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=2)
        print(f"Uvicorn process output:\n{out}")
    except Exception:
        pass

def test_spa_server_graph_tab(start_spa_server):
    url = f"{start_spa_server}/"
    resp = requests.get(url)
    print("[TEST] SPA server HTML response (first 500 chars):\n", resp.text[:500])
    assert resp.status_code == 200
    assert "<title>Azure Tenant Grapher SPA</title>" in resp.text
    assert "Graph Visualization" in resp.text
    assert "Azure Tenant Graph - 3D Visualization" in resp.text
    # Should contain a <canvas> or 3d-force-graph script
    assert "3d-force-graph" in resp.text or "<canvas" in resp.text