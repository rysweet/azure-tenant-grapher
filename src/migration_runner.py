import glob
import os
import re
import time

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

    # Determine applied migrations by checking for applied constraint names
    # (Assume all migrations are idempotent and can be re-run safely)
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
                # Check if any non-comment line starts with a schema keyword
                for line in stmt.split("\n"):
                    stripped = line.strip()
                    if stripped and not stripped.startswith("//"):
                        # Found a non-comment line, check if it's a schema statement
                        return any(
                            stripped.upper().startswith(kw) for kw in schema_keywords
                        )
                # All lines are comments or empty
                return False

            stmts = [s.strip() for s in cypher.split(";") if s.strip()]
            schema_stmts = [s for s in stmts if is_schema_stmt(s)]
            data_stmts = [s for s in stmts if not is_schema_stmt(s)]

            # Run each schema statement in its own driver/session/transaction
            for stmt in schema_stmts:
                driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
                try:
                    with driver.session() as session:

                        def run_schema(tx: ManagedTransaction, stmt: str = stmt):
                            tx.run(stmt)  # type: ignore[arg-type]

                        session.execute_write(run_schema)
                finally:
                    driver.close()
                # Ensure schema change is fully committed before proceeding
                time.sleep(5)

            # Run all data statements in a new process for full isolation
            if data_stmts:
                import subprocess

                data_cypher = ";\n".join(data_stmts)
                script_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "scripts",
                    "run_single_migration.py",
                )
                result = subprocess.run(
                    [
                        "python3",
                        script_path,
                        uri,
                        user,
                        password,
                        str(seq),
                    ],
                    input=data_cypher.encode("utf-8"),
                    capture_output=True,
                )
                if result.returncode != 0:
                    print("Data migration failed:", result.stderr.decode())
                    raise RuntimeError("Data migration failed")
            print(str(f"Applied migration {f}"))
