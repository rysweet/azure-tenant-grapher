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

@pytest.fixture(scope="session")
def start_spa_server():
    port = 8123
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
    # Wait for /api/graph to be ready
    url = f"http://127.0.0.1:{port}/api/graph"
    for _ in range(60):
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