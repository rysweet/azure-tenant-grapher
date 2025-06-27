import pytest
import subprocess
import sys
import time
import requests

@pytest.mark.e2e
def test_spa_index_served():
    port = 54323
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
        url = f"http://127.0.0.1:{port}/"
        for i in range(60):
            if proc.poll() is not None:
                out, _ = proc.communicate(timeout=2)
                print(f"Uvicorn process exited early:\n{out}")
                raise RuntimeError("Uvicorn process exited before readiness.")
            try:
                resp = requests.get(url, timeout=0.5)
                if resp.status_code == 200 and "SPA entrypoint" in resp.text:
                    break
            except Exception:
                pass
            time.sleep(0.1)
        else:
            proc.terminate()
            out, _ = proc.communicate(timeout=2)
            print(f"Uvicorn process output:\n{out}")
            raise TimeoutError("SPA index.html was not served in time")
        # Success
        r = requests.get(url)
        assert r.status_code == 200
        assert "SPA entrypoint" in r.text
        # Also check static file serving
        static_url = f"http://127.0.0.1:{port}/static/index.html"
        r2 = requests.get(static_url)
        assert r2.status_code == 200
        assert "SPA entrypoint" in r2.text
    finally:
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=2)
            print(f"Uvicorn process output:\n{out}")
        except Exception:
            pass