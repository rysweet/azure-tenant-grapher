import os
import subprocess
import sys

import pytest


@pytest.mark.integration
def test_full_narrative_to_graph_integration(tmp_path):
    simdoc_path = tmp_path / "generated-simdoc.md"

    # Check for required LLM environment variables
    required_env = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_KEY",
        "AZURE_OPENAI_API_VERSION",
    ]
    missing = [var for var in required_env if not os.environ.get(var)]
    if missing:
        pytest.skip(
            f"Skipping integration test: missing LLM config: {', '.join(missing)}"
        )

    env = os.environ.copy()
    env["NEO4J_AUTH"] = "neo4j/neo4j"  # pragma: allowlist secret
    env["NEO4J_PASSWORD"] = (
        "neo4j"  # pragma: allowlist secret  # pragma: allowlist secret
    )

    # 1. Generate a realistic narrative markdown using the CLI
    result = subprocess.run(
        [
            sys.executable,
            "scripts/cli.py",
            "generate-sim-doc",
            "--out",
            str(simdoc_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"generate-sim-doc failed: {result.stderr}"

    # 2. Ingest the generated narrative using the CLI
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", "create-tenant", str(simdoc_path)],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        print("DEBUG: create-tenant stdout:\n", result.stdout)
        print("DEBUG: create-tenant stderr:\n", result.stderr)
    assert result.returncode == 0, f"create-tenant failed: {result.stderr}"
