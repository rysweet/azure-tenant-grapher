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
