import pytest
import subprocess
import sys
import time
import requests
from fastapi import FastAPI

@pytest.mark.e2e
def test_minimal_uvicorn_healthz():
    # Write a minimal FastAPI app to a temp file
    import tempfile
    app_code = '''
from fastapi import FastAPI
app = FastAPI()
@app.get("/healthz")
def healthz():
    return {"status": "ok"}
def create_app():
    return app
'''
    # Use the real module path for minimal_app
    port = 54321
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "tests.e2e.minimal_app:create_app",
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
        url = f"http://127.0.0.1:{port}/healthz"
        for i in range(60):
            if proc.poll() is not None:
                out, _ = proc.communicate(timeout=2)
                print(f"Uvicorn process exited early:\n{out}")
                raise RuntimeError("Uvicorn process exited before readiness.")
            try:
                resp = requests.get(url, timeout=0.5)
                if resp.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.1)
        else:
            proc.terminate()
            out, _ = proc.communicate(timeout=2)
            print(f"Uvicorn process output:\n{out}")
            raise TimeoutError("Minimal uvicorn server did not become ready in time")
        # Success
        r = requests.get(url)
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
    finally:
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=2)
            print(f"Uvicorn process output:\n{out}")
        except Exception:
            pass