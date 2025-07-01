import os
import shutil
import subprocess
from typing import Any

import pytest


@pytest.mark.integration
def print_cli_failure(result: Any) -> None:
    print(f"Process exited with code {result.returncode}")
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)


def test_generate_sim_doc_basic(tmp_path):
    # Prepare a minimal seed file
    seed_content = "# Seed\nThis is a test seed for the simulated customer profile."
    seed_file = tmp_path / "seed.md"
    seed_file.write_text(seed_content, encoding="utf-8")

    # Prepare output path
    out_file = tmp_path / "simdoc-test.md"

    # Run the CLI command
    result = subprocess.run(
        [
            "python",
            "scripts/cli.py",
            "generate-sim-doc",
            "--size",
            "123",
            "--seed",
            str(seed_file),
            "--out",
            str(out_file),
        ],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "AZURE_OPENAI_KEY": os.environ.get("AZURE_OPENAI_KEY", "dummy"),
        },
        timeout=120,
    )

    # Check process exit
    if result.returncode != 0:
        print_cli_failure(result)
    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    # Check output file exists and is not empty
    assert out_file.exists(), "Output file was not created"
    content = out_file.read_text(encoding="utf-8")
    assert "company" in content.lower() or "profile" in content.lower(), (
        "Output does not look like a profile"
    )
    assert len(content) > 50, "Output is too short"

    # Clean up simdocs/ if created
    simdocs_dir = "simdocs"
    if os.path.isdir(simdocs_dir) and not os.listdir(simdocs_dir):
        shutil.rmtree(simdocs_dir)
