import glob
import os
import re

from neo4j import GraphDatabase, ManagedTransaction, basic_auth

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")


def run_pending_migrations():
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")
    if not uri or not user or not password:
        print(
            "Neo4j migration skipped: NEO4J_URI, NEO4J_USER, or NEO4J_PASSWORD not set."
        )
        return

    driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
    try:
        # Get current version
        with driver.session() as session:
            result = session.run(
                "MATCH (v:GraphVersion) RETURN v.major AS major, v.minor AS minor ORDER BY v.major DESC, v.minor DESC LIMIT 1"
            )
            row = result.single()
            if row:
                current_major = row["major"]
            else:
                current_major = 0

        # Find migration files
        files = sorted(
            glob.glob(os.path.join(MIGRATIONS_DIR, "[0-9][0-9][0-9][0-9]_*.cypher"))
        )
        for f in files:
            m = re.match(r".*/(\d{4})_.*\.cypher$", f)
            if not m:
                continue
            seq = int(m.group(1))
            if seq > current_major:
                with open(f, encoding="utf-8") as cypher_file:
                    cypher = cypher_file.read()

                def is_schema_stmt(stmt: str) -> bool:
                    schema_keywords = [
                        "CREATE CONSTRAINT",
                        "DROP CONSTRAINT",
                        "CREATE INDEX",
                        "DROP INDEX",
                    ]
                    return any(
                        stmt.strip().upper().startswith(kw) for kw in schema_keywords
                    )

                stmts = [s.strip() for s in cypher.split(";") if s.strip()]
                schema_stmts = [s for s in stmts if is_schema_stmt(s)]
                data_stmts = [s for s in stmts if not is_schema_stmt(s)]

                # Run each schema statement in its own transaction and session
                for stmt in schema_stmts:
                    with driver.session() as session:

                        def run_schema(tx: ManagedTransaction, stmt: str = stmt):
                            tx.run(stmt)

                        session.execute_write(run_schema)

                # Run all data statements in a new session/transaction
                if data_stmts:
                    with driver.session() as session:

                        def run_data(
                            tx: ManagedTransaction,
                            data_stmts: list[str] = data_stmts,
                            seq: int = seq,
                        ):
                            for stmt in data_stmts:
                                tx.run(stmt)
                            tx.run(
                                "MERGE (v:GraphVersion {major:$major, minor:$minor}) "
                                "SET v.appliedAt = datetime()",
                                major=seq,
                                minor=0,
                            )

                        session.execute_write(run_data)
                else:
                    # If only schema changes, still record the migration in a new session
                    with driver.session() as session:

                        def record_version(
                            tx: ManagedTransaction,
                            seq: int = seq,
                        ):
                            tx.run(
                                "MERGE (v:GraphVersion {major:$major, minor:$minor}) "
                                "SET v.appliedAt = datetime()",
                                major=seq,
                                minor=0,
                            )

                        session.execute_write(record_version)

                print(f"Applied migration {f}")
    finally:
        driver.close()
