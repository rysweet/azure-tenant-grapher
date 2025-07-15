import subprocess
import os
import pytest
import time

pytest.importorskip("docker")

@pytest.mark.integration
def test_build_no_dashboard_autostarts_neo4j(tmp_path):
    # remove any running container
    subprocess.run(["docker","rm","-f","azure-tenant-grapher-neo4j"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # run build
    proc = subprocess.run(["uv","run","azure-tenant-grapher","build","--no-dashboard"], text=True)
    assert proc.returncode == 0
    # allow container list settle
    time.sleep(2)
    ps = subprocess.check_output(["docker","ps","--format","{{.Names}}"]).decode()
    assert "azure-tenant-grapher-neo4j" in ps