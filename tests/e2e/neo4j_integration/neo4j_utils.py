"""
Neo4j E2E Test Utilities

Utility functions for Neo4j integration testing.
"""

import hashlib
import json
import logging
import random
import string
import time
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from neo4j import Driver, Session, Transaction
from neo4j.exceptions import Neo4jError, ServiceUnavailable

logger = logging.getLogger(__name__)


def generate_random_data(size: int = 100) -> List[Dict[str, Any]]:
    """
    Generate random test data for Neo4j.

    Args:
        size: Number of records to generate

    Returns:
        List of dictionaries with random data
    """
    data = []
    for i in range(size):
        record = {
            "id": f"id-{i}",
            "name": f"Name-{''.join(random.choices(string.ascii_letters, k=8))}",
            "value": random.randint(1, 1000),
            "timestamp": int(time.time() * 1000) + i,
            "tags": {
                "env": random.choice(["prod", "dev", "test"]),
                "team": random.choice(["alpha", "beta", "gamma"]),
                "priority": random.choice(["high", "medium", "low"])
            },
            "description": ' '.join(random.choices(string.ascii_letters + string.digits, k=50))
        }
        data.append(record)
    return data


def calculate_data_checksum(data: List[Dict[str, Any]]) -> str:
    """
    Calculate checksum for data integrity verification.

    Args:
        data: List of data records

    Returns:
        SHA256 checksum of the data
    """
    # Sort data for consistent checksum
    sorted_data = sorted(data, key=lambda x: x.get("id", ""))
    data_str = json.dumps(sorted_data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()


def verify_data_integrity(session: Session, expected_checksum: str) -> bool:
    """
    Verify data integrity by comparing checksums.

    Args:
        session: Neo4j session
        expected_checksum: Expected data checksum

    Returns:
        True if data integrity is maintained
    """
    result = session.run("MATCH (n:TestNode) RETURN n ORDER BY n.id")
    data = []
    for record in result:
        node = record["n"]
        data.append(dict(node))

    actual_checksum = calculate_data_checksum(data)
    return actual_checksum == expected_checksum


def simulate_network_failure(driver: Driver, failure_duration: float = 2.0) -> None:
    """
    Simulate network failure by forcing connection close.

    Args:
        driver: Neo4j driver
        failure_duration: How long to simulate failure
    """
    # Close all connections
    driver.close()
    time.sleep(failure_duration)


def bulk_insert_nodes(
    session: Session,
    data: List[Dict[str, Any]],
    batch_size: int = 100,
    label: str = "TestNode"
) -> int:
    """
    Bulk insert nodes into Neo4j.

    Args:
        session: Neo4j session
        data: List of node data
        batch_size: Batch size for inserts
        label: Node label

    Returns:
        Number of nodes inserted
    """
    total_inserted = 0

    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        query = f"""
        UNWIND $batch AS node
        CREATE (n:{label})
        SET n = node
        RETURN count(n) as count
        """
        result = session.run(query, batch=batch)
        count = result.single()["count"]
        total_inserted += count

    return total_inserted


def concurrent_write_test(
    driver: Driver,
    num_threads: int = 10,
    writes_per_thread: int = 100
) -> Dict[str, Any]:
    """
    Test concurrent write operations.

    Args:
        driver: Neo4j driver
        num_threads: Number of concurrent threads
        writes_per_thread: Number of writes per thread

    Returns:
        Dictionary with test results
    """
    results = {
        "total_writes": 0,
        "successful_writes": 0,
        "failed_writes": 0,
        "conflicts": 0,
        "duration": 0
    }

    def write_task(thread_id: int) -> Tuple[int, int, int]:
        successful = 0
        failed = 0
        conflicts = 0

        with driver.session() as session:
            for i in range(writes_per_thread):
                try:
                    query = """
                    CREATE (n:ConcurrentNode {
                        thread_id: $thread_id,
                        sequence: $sequence,
                        timestamp: timestamp()
                    })
                    RETURN n
                    """
                    session.run(query, thread_id=thread_id, sequence=i)
                    successful += 1
                except Neo4jError as e:
                    if "conflict" in str(e).lower():
                        conflicts += 1
                    failed += 1

        return successful, failed, conflicts

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [
            executor.submit(write_task, i)
            for i in range(num_threads)
        ]

        for future in as_completed(futures):
            successful, failed, conflicts = future.result()
            results["successful_writes"] += successful
            results["failed_writes"] += failed
            results["conflicts"] += conflicts

    results["duration"] = time.time() - start_time
    results["total_writes"] = results["successful_writes"] + results["failed_writes"]

    return results


def measure_query_performance(
    session: Session,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    iterations: int = 100
) -> Dict[str, float]:
    """
    Measure query performance statistics.

    Args:
        session: Neo4j session
        query: Cypher query to measure
        params: Query parameters
        iterations: Number of iterations

    Returns:
        Performance statistics
    """
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        session.run(query, **(params or {}))
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)  # Convert to milliseconds

    times.sort()

    return {
        "min_ms": min(times),
        "max_ms": max(times),
        "avg_ms": sum(times) / len(times),
        "median_ms": times[len(times) // 2],
        "p95_ms": times[int(len(times) * 0.95)],
        "p99_ms": times[int(len(times) * 0.99)]
    }


def create_backup(driver: Driver, backup_path: str) -> bool:
    """
    Create a backup of the Neo4j database.

    Args:
        driver: Neo4j driver
        backup_path: Path to store backup

    Returns:
        True if backup successful
    """
    try:
        with driver.session() as session:
            # Export all nodes and relationships
            nodes_query = "MATCH (n) RETURN n"
            rels_query = "MATCH ()-[r]->() RETURN r"

            nodes_result = session.run(nodes_query)
            rels_result = session.run(rels_query)

            backup_data = {
                "nodes": [dict(record["n"]) for record in nodes_result],
                "relationships": [
                    {
                        "type": record["r"].type,
                        "properties": dict(record["r"]),
                        "start": record["r"].start_node.id,
                        "end": record["r"].end_node.id
                    }
                    for record in rels_result
                ]
            }

            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)

            return True
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False


def restore_backup(driver: Driver, backup_path: str) -> bool:
    """
    Restore Neo4j database from backup.

    Args:
        driver: Neo4j driver
        backup_path: Path to backup file

    Returns:
        True if restore successful
    """
    try:
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)

        with driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")

            # Restore nodes
            for node_data in backup_data["nodes"]:
                labels = node_data.get("labels", ["Node"])
                label_str = ":".join(labels)
                query = f"CREATE (n:{label_str} $props)"
                session.run(query, props=node_data)

            # Restore relationships
            for rel_data in backup_data["relationships"]:
                query = """
                MATCH (a) WHERE id(a) = $start_id
                MATCH (b) WHERE id(b) = $end_id
                CREATE (a)-[r:""" + rel_data["type"] + """ $props]->(b)
                """
                session.run(
                    query,
                    start_id=rel_data["start"],
                    end_id=rel_data["end"],
                    props=rel_data["properties"]
                )

            return True
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return False


def verify_transaction_isolation(driver: Driver) -> bool:
    """
    Verify transaction isolation levels.

    Args:
        driver: Neo4j driver

    Returns:
        True if transaction isolation is properly maintained
    """
    def transaction1(tx: Transaction) -> None:
        tx.run("CREATE (n:IsolationTest {id: 1, value: 'initial'})")
        time.sleep(2)  # Hold transaction open
        tx.run("MATCH (n:IsolationTest {id: 1}) SET n.value = 'updated'")

    def transaction2(tx: Transaction) -> str:
        time.sleep(1)  # Start after transaction1
        result = tx.run("MATCH (n:IsolationTest {id: 1}) RETURN n.value as value")
        record = result.single()
        return record["value"] if record else None

    # Clean up first
    with driver.session() as session:
        session.run("MATCH (n:IsolationTest) DETACH DELETE n")

    # Run concurrent transactions
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as executor:
        with driver.session() as session1:
            future1 = executor.submit(session1.execute_write, transaction1)

        with driver.session() as session2:
            future2 = executor.submit(session2.execute_read, transaction2)

        future1.result()
        value = future2.result()

    # Verify isolation - transaction2 should not see uncommitted changes
    return value is None or value == "initial"


def stress_test_connections(
    driver: Driver,
    num_connections: int = 100,
    operations_per_connection: int = 10
) -> Dict[str, Any]:
    """
    Stress test Neo4j with multiple concurrent connections.

    Args:
        driver: Neo4j driver
        num_connections: Number of concurrent connections
        operations_per_connection: Operations per connection

    Returns:
        Test results
    """
    results = {
        "total_operations": 0,
        "successful_operations": 0,
        "failed_operations": 0,
        "connection_errors": 0,
        "duration": 0
    }

    def connection_task(conn_id: int) -> Tuple[int, int, int]:
        successful = 0
        failed = 0
        conn_errors = 0

        try:
            with driver.session() as session:
                for op in range(operations_per_connection):
                    try:
                        query = """
                        CREATE (n:StressTest {
                            conn_id: $conn_id,
                            op_id: $op_id,
                            timestamp: timestamp()
                        })
                        RETURN n
                        """
                        session.run(query, conn_id=conn_id, op_id=op)
                        successful += 1
                    except ServiceUnavailable:
                        conn_errors += 1
                        failed += 1
                    except Exception:
                        failed += 1
        except Exception:
            conn_errors += operations_per_connection
            failed += operations_per_connection

        return successful, failed, conn_errors

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=num_connections) as executor:
        futures = [
            executor.submit(connection_task, i)
            for i in range(num_connections)
        ]

        for future in as_completed(futures):
            successful, failed, conn_errors = future.result()
            results["successful_operations"] += successful
            results["failed_operations"] += failed
            results["connection_errors"] += conn_errors

    results["duration"] = time.time() - start_time
    results["total_operations"] = num_connections * operations_per_connection

    return results