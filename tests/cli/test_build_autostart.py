import subprocess
import time

import pytest

pytest.importorskip("subprocess")

# Check for docker presence, skip if not available
try:
    subprocess.run(
        ["docker", "--version"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
except Exception:
    pytest.skip("docker is not available in the environment")


@pytest.mark.integration
def test_build_no_dashboard_autostarts_neo4j(tmp_path):
    # remove any running container
    subprocess.run(
        ["docker", "rm", "-f", "azure-tenant-grapher-neo4j"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # run build with timeout and capture output
    try:
        proc = subprocess.run(
            ["uv", "run", "azure-tenant-grapher", "build", "--no-dashboard"],
            text=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as e:
        # Attempt to kill any lingering process (shouldn't be needed for run, but for completeness)
        pytest.fail(
            f"Process timed out after 120s.\nstdout:\n{getattr(e, 'stdout', '')}\nstderr:\n{getattr(e, 'stderr', '')}"
        )
    # Assert return code and include output for diagnostics
    assert proc.returncode == 0, (
        f"Process failed with return code {proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    # allow container list settle
    time.sleep(2)
    ps = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"]).decode()
    assert "azure-tenant-grapher-neo4j" in ps, (
        f"Container not found in running containers:\n{ps}"
    )
