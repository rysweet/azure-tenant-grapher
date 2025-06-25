import glob
import os
import re

from neo4j import GraphDatabase, basic_auth

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
        with driver.session() as session:
            # Get current version
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
                    from neo4j import ManagedTransaction

                    def apply(
                        tx: ManagedTransaction, cypher: str = cypher, seq: int = seq
                    ):
                        for stmt in [s.strip() for s in cypher.split(";") if s.strip()]:
                            tx.run(str(stmt))
                        tx.run(
                            "MERGE (v:GraphVersion {major:$major, minor:$minor}) "
                            "SET v.appliedAt = datetime()",
                            major=seq,
                            minor=0,
                        )

                    session.execute_write(apply)
                    print(f"Applied migration {f}")
    finally:
        driver.close()
