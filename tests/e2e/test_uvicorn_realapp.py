import pytest
import subprocess
import sys
import time
import requests

@pytest.mark.e2e
def test_uvicorn_realapp_healthz():
    port = 54322
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
            raise TimeoutError("Real uvicorn server did not become ready in time")
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