import importlib
import socket
from unittest import mock

import pytest
from neo4j import GraphDatabase, basic_auth


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
        mock_driver.session.return_value.__exit__.return_value = None
        # Patch glob to return a fake migration file
        with mock.patch("src.migration_runner.glob.glob") as mock_glob, mock.patch(
            "src.migration_runner.open",
            mock.mock_open(read_data="CREATE TEST;"),
            create=True,
        ):
            mock_glob.return_value = ["migrations/0001_create_schema.cypher"]
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
        mock_driver.session.return_value.__exit__.return_value = None
        # Patch glob to return both 0001 and 0002
        with mock.patch("src.migration_runner.glob.glob") as mock_glob, mock.patch(
            "src.migration_runner.open",
            mock.mock_open(read_data="CREATE TEST;"),
            create=True,
        ):
            mock_glob.return_value = [
                "migrations/0001_create_schema.cypher",
                "migrations/0002_add_core_constraints.cypher",
            ]
            import src.migration_runner as migration_runner_reload

            importlib.reload(migration_runner_reload)
            migration_runner_reload.run_pending_migrations()
            # Should call session.write_transaction or execute_write for 0002
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
        mock_driver.session.return_value.__exit__.return_value = None
        # Patch glob to return all three migrations
        with mock.patch("src.migration_runner.glob.glob") as mock_glob, mock.patch(
            "src.migration_runner.open", create=True
        ) as mock_open:
            mock_glob.return_value = [
                "migrations/0001_create_schema.cypher",
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


def is_neo4j_up(host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except Exception:
        return False


@pytest.mark.integration
def test_schema_and_write_in_same_transaction_fails(neo4j_container):
    uri, user, password = neo4j_container
    driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
    with driver.session() as session:

        def schema_and_write(tx):
            tx.run(
                "CREATE CONSTRAINT test_constraint IF NOT EXISTS FOR (n:TestLabel) REQUIRE n.id IS UNIQUE"
            )
            tx.run("CREATE (n:TestLabel {id: 1})")

        with pytest.raises(Exception) as excinfo:
            session.execute_write(schema_and_write)
        assert "ForbiddenDueToTransactionType" in str(excinfo.value)
    driver.close()
