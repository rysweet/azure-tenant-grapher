import sys

from neo4j import GraphDatabase, ManagedTransaction, basic_auth


def run_data_migration(uri, user, password, cypher, seq):
    driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
    try:
        with driver.session() as session:
            stmts = [s.strip() for s in cypher.split(";") if s.strip()]

            def run_data(tx: ManagedTransaction, stmts=stmts, seq=seq):
                for stmt in stmts:
                    tx.run(stmt)
                tx.run(
                    "MERGE (v:GraphVersion {major:$major, minor:$minor}) "
                    "SET v.appliedAt = datetime()",
                    major=seq,
                    minor=0,
                )

            session.execute_write(run_data)
    finally:
        driver.close()


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(
            "Usage: run_single_migration.py <NEO4J_URI> <NEO4J_USER> <NEO4J_PASSWORD> <SEQ>"
        )
        sys.exit(1)
    uri = sys.argv[1]
    user = sys.argv[2]
    password = sys.argv[3]
    seq = int(sys.argv[4])
    cypher = sys.stdin.read()
    run_data_migration(uri, user, password, cypher, seq)
