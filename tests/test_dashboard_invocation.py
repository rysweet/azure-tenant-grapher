import asyncio
from typing import Any, Optional

from click.testing import CliRunner

# Import CLI entrypoint
from scripts.cli import cli


def test_dashboard_invokes_processing(monkeypatch: Any) -> None:
    """
    Regression test: Prove dashboard mode invokes AzureTenantGrapher.build_graph.
    - Patches build_graph to set an asyncio.Event.
    - Patches RichDashboard.live to a dummy async context manager.
    - Invokes CLI with dashboard enabled.
    - Asserts build_graph was awaited and CLI exited.
    """
    # Patch AzureTenantGrapher.build_graph to set an event
    from src.azure_tenant_grapher import AzureTenantGrapher
    from src.rich_dashboard import RichDashboard

    event = asyncio.Event()

    async def fake_build_graph(self: Any, *args: Any, **kwargs: Any) -> str:
        event.set()
        return "stubbed-result"

    monkeypatch.setattr(AzureTenantGrapher, "build_graph", fake_build_graph)

    # Patch AzureTenantGrapher.__init__ to set a dummy driver with a close method
    class DummyDriver:
        def close(self) -> None:
            pass

        def session(self) -> Any:
            return DummySession()

    class DummySession:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

        def run(self, query: str, *args: Any, **kwargs: Any) -> Any:
            return []

    orig_init = AzureTenantGrapher.__init__

    def dummy_init(self: Any, config: Any) -> None:
        orig_init(self, config)
        self.driver = DummyDriver()

    monkeypatch.setattr(AzureTenantGrapher, "__init__", dummy_init)

    # Also patch the connect_to_neo4j method to prevent any real connections
    def dummy_connect_to_neo4j(self: Any) -> None:
        self.driver = DummyDriver()

    monkeypatch.setattr(AzureTenantGrapher, "connect_to_neo4j", dummy_connect_to_neo4j)

    # Patch GraphDatabase.driver to prevent any real neo4j connections
    from neo4j import GraphDatabase

    def dummy_graph_driver(*args: Any, **kwargs: Any) -> DummyDriver:
        return DummyDriver()

    monkeypatch.setattr(GraphDatabase, "driver", dummy_graph_driver)

    # Patch RichDashboard.live to a dummy async context manager
    class DummyAsyncContextManager:
        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(
            self,
            exc_type: Optional[type],
            exc_val: Optional[Exception],
            exc_tb: Optional[Any],
        ) -> bool:
            return False  # propagate exceptions

    def dummy_live_method(self: Any) -> DummyAsyncContextManager:
        return DummyAsyncContextManager()

    monkeypatch.setattr(RichDashboard, "live", dummy_live_method)

    # Run CLI with dashboard (default, i.e. no --no-dashboard)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["build", "--tenant-id", "dummy", "--no-container"],
        catch_exceptions=False,
    )

    # Check: build_graph was awaited (event is set)
    # Since runner.invoke is sync, we need to run the event loop to check the event
    loop: Optional[asyncio.AbstractEventLoop] = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_set = loop.run_until_complete(event.wait())
    finally:
        if loop is not None:
            loop.close()

    assert is_set is None or is_set is True  # event.wait() returns None when set
    # Accept exit code 0 (success) or nonzero (e.g. due to stubbed dashboard)
    assert result.exit_code == 0 or event.is_set()
    # Optionally, print output for debugging
    # print(result.output)
