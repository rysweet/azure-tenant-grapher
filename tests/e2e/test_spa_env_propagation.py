import os
import subprocess
import sys
import time
import socket

def test_spa_server_env_propagation():
    # Start a Neo4j testcontainer and set NEO4J_URI
    from testcontainers.neo4j import Neo4jContainer
    container = Neo4jContainer("neo4j:4.4.12").with_env("NEO4J_AUTH", "neo4j/neo4j")
    container.start()
    bolt_url = container.get_connection_url()
    user = "neo4j"
    password = "neo4j"
    os.environ["NEO4J_URI"] = bolt_url
    os.environ["NEO4J_USER"] = user
    os.environ["NEO4J_PASSWORD"] = password
    print(f"[TEST] Neo4j testcontainer running at {bolt_url} (user: {user}, password: {password})")

    # Find a random free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    env = os.environ.copy()
    print(f"[TEST] SPA server environment: {env}")

    # Start the SPA server using the CLI command
    proc = subprocess.Popen(
        [
            sys.executable, "scripts/cli.py", "app", "--port", str(port)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    # Wait for the SPA server to print the NEO4J_URI
    found = False
    for _ in range(60):
        if proc.poll() is not None:
            break
        line = proc.stdout.readline()
        print(line.strip())
        if "[DEBUG] Server startup NEO4J_URI:" in line:
            found = True
            if bolt_url not in line:
                assert False, f"SPA server did not see correct NEO4J_URI: {line.strip()}"
            break
        time.sleep(0.2)
    proc.terminate()
    container.stop()
    assert found, "SPA server did not print NEO4J_URI at startup"
import os
import sys
import subprocess
import socket
import time
import requests

def test_spa_server_fails_without_neo4j_uri():
    """
    This test ensures that if NEO4J_URI is not set, the SPA server attempts to connect to the default
    bolt://localhost:7687 and fails, logging the connection error.
    """
    # Unset NEO4J_* env vars
    env = os.environ.copy()
    for k in list(env.keys()):
        if k.startswith("NEO4J_"):
            del env[k]

    # Find a random free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    proc = subprocess.Popen(
        [sys.executable, "scripts/cli.py", "app", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    # Wait for process to exit or timeout
    try:
        outs, _ = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.terminate()
        outs, _ = proc.communicate(timeout=2)

    output = outs or ""
    assert proc.returncode != 0, "SPA server did not exit with error when NEO4J_URI was missing"
    assert (
        "NEO4J_URI environment variable must be set. Refusing to default to localhost:7687" in output
    ), (
        "SPA server did not fail fast with missing NEO4J_URI as expected.\nOutput:\n" + output
    )
import tempfile
import shutil

def test_spa_server_loads_dotenv(monkeypatch):
    """
    This test ensures that if a .env file is present with NEO4J_URI, the CLI and server pick it up.
    """
    import os
    import sys
    import subprocess

    # Create a temp directory and .env file
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = os.path.join(tmpdir, ".env")
        port = "50123"
        bolt_url = f"bolt://localhost:{port}"
        with open(env_path, "w") as f:
            f.write(f"NEO4J_URI={bolt_url}\n")
            f.write("NEO4J_USER=neo4j\n")
            f.write("NEO4J_PASSWORD=neo4j\n")
        with open(env_path, "r") as f:
            print("[TEST DEBUG] .env contents:\n" + f.read())

        # Copy scripts/cli.py to temp dir for isolation
        cli_path = os.path.join(tmpdir, "cli.py")
        shutil.copyfile("scripts/cli.py", cli_path)

        # Run CLI in temp dir (should pick up .env)
        proc = subprocess.Popen(
            [sys.executable, "cli.py", "app", "--port", port],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        found = False
        output_lines = []
        for _ in range(50):
            if proc.poll() is not None:
                break
            line = proc.stdout.readline()
            output_lines.append(line)
            if f"[DEBUG] CLI startup NEO4J_URI: {bolt_url}" in line:
                found = True
                break
            time.sleep(0.2)
        proc.terminate()
        output = "".join(output_lines)
        assert found, (
            f"CLI/server did not pick up NEO4J_URI from .env. Output:\n{output}"
        )
def test_spa_server_serves_graph_from_dotenv():
    """
    This test ensures the app loads NEO4J_URI from .env, connects to Neo4j, and serves the graph at /api/graph.
    """
    import tempfile
    import shutil
    import socket
    import subprocess
    import time
    import requests
    from src.container_manager import Neo4jContainerManager

    # Use the project's Neo4j manager to ensure a running instance
    manager = Neo4jContainerManager()
    running = manager.is_neo4j_container_running()
    print(f"[TEST DEBUG] is_neo4j_container_running: {running}")
    print(f"[TEST DEBUG] manager.neo4j_uri: {manager.neo4j_uri}")
    print(f"[TEST DEBUG] manager.neo4j_user: {manager.neo4j_user}")
    print(f"[TEST DEBUG] manager.neo4j_password: {manager.neo4j_password}")
    assert running, "Neo4j container is not running (ensure it is started via project tooling)"

    bolt_url = manager.neo4j_uri
    user = manager.neo4j_user
    password = manager.neo4j_password

    print(f"[TEST DEBUG] Using Neo4j at {bolt_url} with user={user} password={password}")

    # Load a sample graph
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(bolt_url, auth=(user, password))
    with driver.session() as session:
        session.run("CREATE (n:TestNode {name: 'test'})")
    driver.close()

    # Create temp dir and .env
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = os.path.join(tmpdir, ".env")
        with open(env_path, "w") as f:
            f.write(f"NEO4J_URI={bolt_url}\n")
            f.write(f"NEO4J_USER={user}\n")
            f.write(f"NEO4J_PASSWORD={password}\n")
        with open(env_path, "r") as f:
            print("[TEST DEBUG] .env contents:\n" + f.read())

        # Find a random free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

        # Copy scripts/cli.py to temp dir for isolation
        cli_path = os.path.join(tmpdir, "cli.py")
        shutil.copyfile("scripts/cli.py", cli_path)

        # Start the SPA server
        proc = subprocess.Popen(
            [sys.executable, "cli.py", "app", "--port", str(port)],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Wait for server to start
        started = False
        for _ in range(50):
            if proc.poll() is not None:
                break
            line = proc.stdout.readline()
            if f"Starting SPA server on http://localhost:{port}" in line:
                started = True
                break
            time.sleep(0.2)
        assert started, "SPA server did not start"

        # Query /api/graph
        for _ in range(10):
            try:
                resp = requests.get(f"http://localhost:{port}/api/graph", timeout=2)
                if resp.status_code == 200 and "nodes" in resp.json():
                    break
            except Exception:
                time.sleep(0.5)
        else:
            proc.terminate()
            raise AssertionError("Could not get /api/graph from SPA server")

        data = resp.json()
        proc.terminate()
        assert any(n.get("name") == "test" for n in data.get("nodes", [])), (
            f"SPA server did not serve the expected graph. Response: {data}"
        )
def test_neo4j_manager_connectivity():
    """
    Step 1: Minimal test to verify Neo4jContainerManager can connect to Neo4j and create/read a node.
    """
    import time
    from src.container_manager import Neo4jContainerManager
    from neo4j import GraphDatabase

    manager = Neo4jContainerManager()
    print(f"[STEP1] is_neo4j_container_running: {manager.is_neo4j_container_running()}")
    print(f"[STEP1] manager.neo4j_uri: {manager.neo4j_uri}")
    print(f"[STEP1] manager.neo4j_user: {manager.neo4j_user}")
    print(f"[STEP1] manager.neo4j_password: {manager.neo4j_password}")

    assert manager.is_neo4j_container_running(), "Neo4j container is not running (ensure it is started via project tooling)"

    uri = manager.neo4j_uri
    user = manager.neo4j_user
    password = manager.neo4j_password

    print(f"[STEP1] Connecting to Neo4j at {uri} with user={user} password={password}")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.run("CREATE (n:TestNode {name: 'step1'})")
        result = session.run("MATCH (n:TestNode {name: 'step1'}) RETURN n")
        nodes = list(result)
        print(f"[STEP1] Query result: {nodes}")
        assert nodes, "Failed to create/read node in Neo4j via Neo4jContainerManager"
    driver.close()
def test_spa_server_starts_with_dummy_env():
    """
    Step 2: Minimal test to verify the SPA server can start and print debug output with a dummy .env (no Neo4j connection).
    """
    import tempfile
    import shutil
    import socket
    import subprocess
    import time

    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = os.path.join(tmpdir, ".env")
        with open(env_path, "w") as f:
            f.write("NEO4J_URI=bolt://localhost:9999\n")
            f.write("NEO4J_USER=neo4j\n")
            f.write("NEO4J_PASSWORD=wrong\n")
        with open(env_path, "r") as f:
            print("[STEP2] .env contents:\n" + f.read())

        # Find a random free port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            port = s.getsockname()[1]

        # Copy scripts/cli.py to temp dir for isolation
        cli_path = os.path.join(tmpdir, "cli.py")
        shutil.copyfile("scripts/cli.py", cli_path)

        # Start the SPA server
        proc = subprocess.Popen(
            [sys.executable, "cli.py", "app", "--port", str(port)],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Wait for server to print debug output
        output_lines = []
        for _ in range(50):
            if proc.poll() is not None:
                break
            line = proc.stdout.readline()
            output_lines.append(line)
            print(f"[STEP2] SPA server output: {line.strip()}")
            if "Starting SPA server on" in line:
                break
            time.sleep(0.2)
        proc.terminate()
        assert any("Starting SPA server on" in l for l in output_lines), (
            f"SPA server did not print startup message. Output:\n{''.join(output_lines)}"
        )