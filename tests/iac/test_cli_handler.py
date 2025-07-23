from unittest.mock import MagicMock

from src.iac.cli_handler import get_neo4j_driver_from_config


def test_get_driver_returns_driver(monkeypatch):
    fake_driver = MagicMock()

    class FakeManager:
        def __init__(self, *a, **kw):
            self._driver = None

        def connect(self):
            self._driver = fake_driver

    monkeypatch.setattr(
        "src.iac.cli_handler.create_session_manager", lambda cfg: FakeManager()
    )
    monkeypatch.setattr(
        "src.iac.cli_handler.create_neo4j_config_from_env", lambda: MagicMock()
    )

    driver = get_neo4j_driver_from_config()
    assert driver is fake_driver


import pytest
from unittest.mock import patch
from click.testing import CliRunner
from scripts.cli import cli


@pytest.mark.parametrize(
    "args,expected",
    [
        ([], "manual"),  # default
        (["--aad-mode", "none"], "none"),
        (["--aad-mode", "manual"], "manual"),
        (["--aad-mode", "auto"], "auto"),
    ],
)
def test_generate_iac_aad_mode_flag(args, expected):
    # Patch the async handler to capture the aad_mode argument
    with patch("src.iac.cli_handler.generate_iac_command_handler") as mock_handler:
        mock_handler.return_value = 0  # Simulate success
        runner = CliRunner()
        # Required minimal args for generate-iac to parse
        result = runner.invoke(
            cli,
            ["generate-iac", "--tenant-id", "dummy-tenant", *args],
        )
        assert result.exit_code == 0
        # The handler should have been called once
        assert mock_handler.call_count == 1
        # Extract the aad_mode argument from the call
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["aad_mode"] == expected
