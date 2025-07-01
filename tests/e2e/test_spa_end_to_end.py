import os
import pytest
import subprocess
import sys
import time
import requests
from tests.e2e.conftest import neo4j_test_container

@pytest.fixture(scope="session", autouse=True)
def ensure_neo4j(neo4j_test_container):
    from neo4j import GraphDatabase
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session(database="neo4j") as session:
        session.run("""
            CREATE (a:Resource {id: 'a', name: 'A', type: 'TestType'})
            CREATE (b:Resource {id: 'b', name: 'B', type: 'TestType'})
            CREATE (a)-[:CONNECTED_TO]->(b)
        """)
    driver.close()

import socket

@pytest.fixture(scope="session")
def start_spa_server(neo4j_test_container):
    # Find a random free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    import os
    env = os.environ.copy()
    print(f"[TEST] SPA server environment: {env}")
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
        env=env,
    )
    # Wait for /api/graph to be ready
    url = f"http://127.0.0.1:{port}/api/graph"
    for _ in range(180):  # Wait up to 36 seconds
        if proc.poll() is not None:
            out, _ = proc.communicate(timeout=2)
            print(f"Uvicorn process exited early:\n{out}")
            assert False, "Uvicorn process exited before readiness."
        try:
            resp = requests.get(url, timeout=0.5)
            if resp.status_code == 200 and "nodes" in resp.json():
                break
        except Exception:
            pass
        time.sleep(0.2)
    else:
        proc.terminate()
        out, _ = proc.communicate(timeout=2)
        print(f"Uvicorn process output:\n{out}")
        assert False, "SPA server did not become ready in time"
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=2)
        print(f"Uvicorn process output:\n{out}")
    except Exception:
        pass

def test_spa_graph_data_and_ui(start_spa_server):
    url = f"{start_spa_server}/api/graph"
    resp = requests.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data and "links" in data
    assert len(data["nodes"]) > 0
    assert len(data["links"]) > 0

    # Optionally, use Playwright MCP to validate UI (pseudo-code, not run here)
    # from playwright.sync_api import sync_playwright
    # with sync_playwright() as p:
    #     browser = p.chromium.launch()
    #     page = browser.new_page()
    #     page.goto(start_spa_server)
    #     assert page.locator("#visualization canvas").is_visible()
    #     browser.close()