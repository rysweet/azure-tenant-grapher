from typing import Optional
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from scripts.cli import cli

from src.iac.cli_handler import get_neo4j_driver_from_config


def test_get_driver_returns_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_driver = MagicMock()

    class FakeManager:
        def __init__(self, *a: object, **kw: object) -> None:
            self._driver = None

        def connect(self) -> None:
            self._driver = fake_driver

    monkeypatch.setattr(
        "src.iac.cli_handler.create_session_manager",
        lambda cfg: FakeManager(),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        "src.iac.cli_handler.create_neo4j_config_from_env", lambda: MagicMock()
    )

    driver = get_neo4j_driver_from_config()
    assert driver is fake_driver


def test_generate_iac_default_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI parsing for generate-iac with default AAD mode (manual)."""
    called = {}

    async def mock_generate_iac_command_handler(
        tenant_id: Optional[str] = None,
        format_type: str = "terraform",
        output_path: Optional[str] = None,
        rules_file: Optional[str] = None,
        dry_run: bool = False,
        resource_filters: Optional[str] = None,
        subset_filter: Optional[str] = None,
        node_ids: Optional[list[str]] = None,
        dest_rg: Optional[str] = None,
        location: Optional[str] = None,
        domain_name: Optional[str] = None,
    ) -> int:
        called["tenant_id"] = tenant_id
        return 0

    # Mock at the correct import location in the CLI script
    monkeypatch.setattr(
        "scripts.cli.generate_iac_command_handler",
        mock_generate_iac_command_handler,
    )

    # Also mock the tool check
    monkeypatch.setattr(
        "src.utils.cli_installer.ensure_tool",
        lambda tool, auto_prompt=False: None,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["generate-iac", "--tenant-id", "dummy-tenant"],
    )
    assert result.exit_code == 0
    assert called["tenant_id"] == "dummy-tenant"
