import os
import subprocess
import sys
from typing import Any

import pytest


@pytest.mark.integration
def print_cli_failure(result: Any, label: str = "") -> None:
    if label:
        print(f"--- {label} ---")
    print(f"Process exited with code {result.returncode}")
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)


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
    if result.returncode != 0:
        print_cli_failure(result, "generate-sim-doc")
    assert result.returncode == 0, f"generate-sim-doc failed: {result.stderr}"

    # 2. Ingest the generated narrative using the CLI
    result = subprocess.run(
        [sys.executable, "scripts/cli.py", "create-tenant", str(simdoc_path)],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        print_cli_failure(result, "create-tenant")
    assert result.returncode == 0, f"create-tenant failed: {result.stderr}"
