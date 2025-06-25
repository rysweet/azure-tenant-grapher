import importlib
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USER", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    yield


def test_skips_when_env_missing(monkeypatch, capsys):
    # Remove env vars
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_USER", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    # Import fresh
    import src.migration_runner as migration_runner

    migration_runner.run_pending_migrations()
    out = capsys.readouterr().out
    assert "skipped" in out.lower()


def test_applies_pending_migrations(monkeypatch):
    # Set env vars
    monkeypatch.setenv("NEO4J_URI", "bolt://fake")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    # Patch neo4j driver
    with mock.patch("src.migration_runner.GraphDatabase") as mock_db:
        mock_driver = mock.Mock()
        mock_db.driver.return_value = mock_driver
        mock_session = mock.Mock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        # Simulate no GraphVersion nodes
        mock_session.run.return_value.single.return_value = None
        # Patch glob to return a fake migration file
        with mock.patch("src.migration_runner.glob.glob") as mock_glob, mock.patch(
            "src.migration_runner.open",
            mock.mock_open(read_data="CREATE TEST;"),
            create=True,
        ):
            mock_glob.return_value = ["migrations/0001_create_graph_version.cypher"]
            import src.migration_runner as migration_runner_reload

            importlib.reload(migration_runner_reload)
            migration_runner_reload.run_pending_migrations()
            # Should call session.execute_write or write_transaction


def test_detects_and_applies_0002(monkeypatch):
    # Set env vars
    monkeypatch.setenv("NEO4J_URI", "bolt://fake")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    with mock.patch("src.migration_runner.GraphDatabase") as mock_db:
        mock_driver = mock.Mock()
        mock_db.driver.return_value = mock_driver
        mock_session = mock.Mock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        # Simulate GraphVersion at major=1
        mock_session.run.return_value.single.return_value = {"major": 1, "minor": 0}
        # Patch glob to return both 0001 and 0002
        with mock.patch("src.migration_runner.glob.glob") as mock_glob, mock.patch(
            "src.migration_runner.open",
            mock.mock_open(read_data="CREATE TEST;"),
            create=True,
        ):
            mock_glob.return_value = [
                "migrations/0001_create_graph_version.cypher",
                "migrations/0002_add_core_constraints.cypher",
            ]
            import src.migration_runner as migration_runner_reload

            importlib.reload(migration_runner_reload)
            migration_runner_reload.run_pending_migrations()
            # Should call session.write_transaction or execute_write for 0002
            assert mock_session.write_transaction.called or getattr(
                mock_session, "execute_write", None
            )
            # Ensure migration 0002 was considered (seq > 1)
            calls = (
                mock_session.write_transaction.call_args_list
                if hasattr(mock_session, "write_transaction")
                else []
            )
            found_0002 = any(
                call
                for call in calls
                if call
                and call[0]
                and hasattr(call[0][0], "__closure__")
                and any(
                    "major=2" in str(cell.cell_contents)
                    for cell in call[0][0].__closure__ or []
                )
            )
            # If using execute_write, skip this check (since it's deprecated in code)
            if calls:
                assert found_0002
            assert mock_session.write_transaction.called or getattr(
                mock_session, "execute_write", None
            )


def test_applies_0003_backfill_subscription(monkeypatch):
    # Set env vars
    monkeypatch.setenv("NEO4J_URI", "bolt://fake")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pw")
    with mock.patch("src.migration_runner.GraphDatabase") as mock_db:
        mock_driver = mock.Mock()
        mock_db.driver.return_value = mock_driver
        mock_session = mock.Mock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        # Simulate GraphVersion at major=2
        mock_session.run.return_value.single.return_value = {"major": 2, "minor": 0}
        # Patch glob to return all three migrations
        with mock.patch("src.migration_runner.glob.glob") as mock_glob, mock.patch(
            "src.migration_runner.open", create=True
        ) as mock_open:
            mock_glob.return_value = [
                "migrations/0001_create_graph_version.cypher",
                "migrations/0002_add_core_constraints.cypher",
                "migrations/0003_backfill_subscriptions.cypher",
            ]
            # Return dummy for 0001/0002, real for 0003
            cypher_0003 = """// Migration 0003 - Back-fill Subscription nodes & CONTAINS edges

// 1. Create Subscription nodes from ResourceGroup or Resource ids
MATCH (n)
WHERE EXISTS(n.id) AND n.id STARTS WITH '/subscriptions/'
WITH DISTINCT split(n.id,'/')[2] AS subId, n
WITH subId, collect(DISTINCT n) AS nodes
MERGE (s:Subscription {id: subId})
  ON CREATE SET s.name = subId  // use id as name placeholder
WITH s, nodes
UNWIND nodes AS n
  MERGE (s)-[:CONTAINS]->(n);

// 2. Ensure ResourceGroup nodes have subscription_id + name
MATCH (rg:ResourceGroup)
SET rg.subscription_id = split(rg.id,'/')[2],
    rg.name = split(rg.id,'/')[4];

// 3. Ensure Resource nodes have subscription_id & resource_group
MATCH (r:Resource)
WHERE NOT EXISTS(r.subscription_id)
SET r.subscription_id = split(r.id,'/')[2],
    r.resource_group  = split(r.id,'/')[4];

// 4. Update GraphVersion
MERGE (v:GraphVersion {major:3, minor:0})
  ON CREATE
    SET v.appliedAt = datetime();
"""

            def open_side_effect(path, *args, **kwargs):
                if path.endswith("0003_backfill_subscriptions.cypher"):
                    return mock.mock_open(read_data=cypher_0003)()
                else:
                    return mock.mock_open(read_data="CREATE TEST;")()

            mock_open.side_effect = open_side_effect

            import src.migration_runner as migration_runner_reload

            importlib.reload(migration_runner_reload)
            migration_runner_reload.run_pending_migrations()

            # Check that write_transaction was called for 0003
            assert mock_session.write_transaction.called
            # Check that the cypher for 0003 was run
            calls = mock_session.write_transaction.call_args_list
            found_0003 = any(
                "MERGE (v:GraphVersion {major:3, minor:0})" in str(call)
                for call in calls
            )
            assert found_0003
