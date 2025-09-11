import subprocess
from unittest.mock import patch

import pytest

import src.utils.cli_installer as cli_installer


@pytest.mark.usefixtures("monkeypatch")
class TestGenerateIacAutoDoctor:
    def test_ensure_tool_invoked_when_terraform_missing(self, monkeypatch):
        # Simulate terraform missing, ensure install_tool is called
        monkeypatch.setattr(cli_installer.shutil, "which", lambda name: None)
        called = {}

        def fake_install_tool(tool):
            called["tool"] = tool
            return False  # Simulate user declines install

        monkeypatch.setattr(cli_installer, "install_tool", fake_install_tool)
        # Ensure terraform is registered for this test
        assert "terraform" in cli_installer.TOOL_REGISTRY
        with pytest.raises(SystemExit):
            cli_installer.ensure_tool("terraform", auto_prompt=True)
        assert called["tool"] == "terraform"

    @pytest.mark.skip(
        reason="Subprocess tests can't use monkeypatch - would need environment variable approach"
    )
    def test_generate_iac_aborts_if_user_declines_install(self, monkeypatch):
        # Patch which to return None for terraform, simulate user declines install
        monkeypatch.setattr(
            cli_installer.shutil,
            "which",
            lambda name: None if name == "terraform" else "/bin/true",
        )
        monkeypatch.setattr(cli_installer, "is_tool_installed", lambda tool: False)
        monkeypatch.setattr(
            cli_installer, "install_tool", lambda tool: False
        )  # User declines

        # Ensure terraform is registered for this test
        assert "terraform" in cli_installer.TOOL_REGISTRY

        result = subprocess.run(
            [
                "uv",
                "run",
                "scripts/cli.py",
                "generate-iac",
                "--format",
                "terraform",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert (
            "Aborting: 'terraform' is required but was not installed." in result.stdout
        )

    @pytest.mark.skip(
        reason="Subprocess tests can't use monkeypatch - would need environment variable approach"
    )
    def test_generate_iac_runs_install_tool_when_missing(self, monkeypatch):
        # Patch which to return None for terraform, simulate user accepts install
        monkeypatch.setattr(
            cli_installer.shutil,
            "which",
            lambda name: None if name == "terraform" else "/bin/true",
        )
        monkeypatch.setattr(cli_installer, "is_tool_installed", lambda tool: False)
        called = {}

        def fake_install_tool(tool):
            called["tool"] = tool
            return True  # Simulate user accepts install

        monkeypatch.setattr(cli_installer, "install_tool", fake_install_tool)

        # Ensure terraform is registered for this test
        assert "terraform" in cli_installer.TOOL_REGISTRY

        # Patch generate_iac_command_handler to avoid running real logic
        with patch("scripts.cli.generate_iac_command_handler", return_value=None):
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "scripts/cli.py",
                    "generate-iac",
                    "--format",
                    "terraform",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
            )
        assert result.returncode == 0
        assert called["tool"] == "terraform"
