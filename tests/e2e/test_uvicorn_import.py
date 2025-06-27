import pytest
import subprocess
import sys

@pytest.mark.e2e
def test_uvicorn_import_realapp():
    # Just try to import the app module in a subprocess and print result
    proc = subprocess.Popen(
        [
            sys.executable, "-c",
            "from src.visualization.server import create_app; print('IMPORT_OK')"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out, _ = proc.communicate(timeout=5)
    print("IMPORT subprocess output:\n", out)
    assert "IMPORT_OK" in out
    assert proc.returncode == 0