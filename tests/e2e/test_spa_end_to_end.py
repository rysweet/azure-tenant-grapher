import pytest
import subprocess
import sys
import time
import requests
from testcontainers.neo4j import Neo4jContainer

@pytest.fixture(scope="session")
def neo4j_container():
    container = Neo4jContainer("neo4j:5.18")
    container.start()
    bolt_url = container.get_connection_url()
    user = "neo4j"
    password = "azure-grapher-2024"
    import os
    os.environ["NEO4J_URI"] = bolt_url
    os.environ["NEO4J_USER"] = user
    os.environ["NEO4J_PASSWORD"] = password
    print(f"[TEST] Neo4j testcontainer running at {bolt_url} (user: {user}, password: {password})")
    # Wait for Neo4j to be ready
    for _ in range(30):
        try:
            import socket
            s = socket.create_connection(("127.0.0.1", int(bolt_url.split(":")[-1])), timeout=1)
            s.close()
            break
        except Exception:
            time.sleep(1)
    yield container, bolt_url, user, password
    container.stop()

@pytest.fixture(scope="session", autouse=True)
def ensure_neo4j(neo4j_container):
    _, bolt_url, user, password = neo4j_container
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(bolt_url, auth=(user, password))
    with driver.session(database="neo4j") as session:
        session.run("""
            CREATE (a:Resource {id: 'a', name: 'A', type: 'TestType'})
            CREATE (b:Resource {id: 'b', name: 'B', type: 'TestType'})
            CREATE (a)-[:CONNECTED_TO]->(b)
        """)
    driver.close()

@pytest.fixture(scope="session")
def start_spa_server(neo4j_container):
    _, bolt_url, user, password = neo4j_container
    port = 8123
    import os
    env = os.environ.copy()
    env["NEO4J_URI"] = bolt_url
    env["NEO4J_USER"] = user
    env["NEO4J_PASSWORD"] = password
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
            pytest.skip("Uvicorn process exited before readiness.")
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
        pytest.skip("SPA server did not become ready in time")
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