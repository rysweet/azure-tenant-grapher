"""
Test concurrent database access to verify thread safety of the session manager refactor.

This test is designed to detect the BufferError and protocol errors that were
occurring when Neo4j sessions were shared across threads.
"""

import threading
import time
from typing import Any, List
from unittest.mock import Mock

import pytest

from src.resource_processor import DatabaseOperations, ResourceProcessor, ResourceState


class ThreadSafeSessionManager:
    """Mock session manager that tracks concurrent access and simulates thread safety."""

    def __init__(self):
        self.session_count = 0
        self.active_sessions = set()
        self.session_lock = threading.Lock()
        self.access_log = []

    def session(self):
        """Context manager that creates a new session for each call."""
        return ThreadSafeSession(self)


class ThreadSafeSession:
    """Mock session that tracks concurrent usage."""

    def __init__(self, manager: ThreadSafeSessionManager):
        self.manager = manager
        self.session_id = None
        self.thread_id = threading.get_ident()

    def __enter__(self):
        with self.manager.session_lock:
            self.manager.session_count += 1
            self.session_id = self.manager.session_count
            self.manager.active_sessions.add(self.session_id)
            self.manager.access_log.append(
                {
                    "action": "session_created",
                    "session_id": self.session_id,
                    "thread_id": self.thread_id,
                    "timestamp": time.time(),
                }
            )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        with self.manager.session_lock:
            self.manager.active_sessions.discard(self.session_id)
            self.manager.access_log.append(
                {
                    "action": "session_closed",
                    "session_id": self.session_id,
                    "thread_id": self.thread_id,
                    "timestamp": time.time(),
                }
            )

    def run(self, query: str, **params: Any) -> Mock:
        """Mock database query that simulates work and tracks access."""
        with self.manager.session_lock:
            self.manager.access_log.append(
                {
                    "action": "query_executed",
                    "session_id": self.session_id,
                    "thread_id": self.thread_id,
                    "query": query[:50] + "..." if len(query) > 50 else query,
                    "timestamp": time.time(),
                }
            )

        # Simulate some database work
        time.sleep(0.001)

        # Return mock result
        mock_result = Mock()
        mock_result.single.return_value = {"count": 1}
        return mock_result


class TestConcurrentDatabaseAccess:
    """Test suite for concurrent database access patterns."""

    def test_concurrent_resource_state_operations(self):
        """Test that ResourceState operations are thread-safe."""
        session_manager = ThreadSafeSessionManager()
        resource_state = ResourceState(session_manager)

        def worker_task(worker_id: int, results: List[bool]):
            """Worker function that performs multiple resource state operations."""
            try:
                for i in range(5):
                    resource_id = f"worker-{worker_id}-resource-{i}"

                    # Test resource_exists
                    resource_state.resource_exists(resource_id)

                    # Test has_llm_description
                    resource_state.has_llm_description(resource_id)

                    # Test get_processing_metadata
                    resource_state.get_processing_metadata(resource_id)

                    # Small delay to increase chance of concurrent access
                    time.sleep(0.001)

                results[worker_id] = True
            except Exception as e:
                print(f"Worker {worker_id} failed: {e}")
                results[worker_id] = False

        # Run multiple threads concurrently
        num_workers = 10
        results = [False] * num_workers
        threads = []

        for worker_id in range(num_workers):
            thread = threading.Thread(target=worker_task, args=(worker_id, results))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)  # 10 second timeout

        # Verify all workers completed successfully
        assert all(results), f"Some workers failed: {results}"

        # Verify no sessions were shared between threads
        thread_sessions = {}
        for log_entry in session_manager.access_log:
            if log_entry["action"] == "query_executed":
                thread_id = log_entry["thread_id"]
                session_id = log_entry["session_id"]

                if thread_id not in thread_sessions:
                    thread_sessions[thread_id] = set()
                thread_sessions[thread_id].add(session_id)

        # Each thread should have used its own sessions
        all_sessions_used = set()
        for _thread_id, sessions in thread_sessions.items():
            # Check no session overlap between threads
            for session_id in sessions:
                assert (
                    session_id not in all_sessions_used
                ), f"Session {session_id} was shared between threads"
                all_sessions_used.add(session_id)

        print(
            f"✅ Concurrent test passed: {num_workers} threads, {len(all_sessions_used)} unique sessions"
        )

    def test_concurrent_database_operations(self):
        """Test that DatabaseOperations are thread-safe."""
        session_manager = ThreadSafeSessionManager()
        db_ops = DatabaseOperations(session_manager)

        def worker_task(worker_id: int, results: List[bool]):
            """Worker function that performs database operations."""
            try:
                for i in range(3):
                    resource = {
                        "id": f"worker-{worker_id}-resource-{i}",
                        "name": f"Test Resource {worker_id}-{i}",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                        "resource_group": f"rg-{worker_id}",
                        "subscription_id": f"sub-{worker_id}",
                    }

                    # Test upsert_resource
                    db_ops.upsert_resource(resource)

                    # Test create_subscription_relationship
                    db_ops.create_subscription_relationship(
                        resource["subscription_id"], resource["id"]
                    )

                    # Test create_resource_group_relationships
                    db_ops.create_resource_group_relationships(resource)

                    time.sleep(0.001)

                results[worker_id] = True
            except Exception as e:
                print(f"Database worker {worker_id} failed: {e}")
                results[worker_id] = False

        # Run multiple threads concurrently
        num_workers = 8
        results = [False] * num_workers
        threads = []

        for worker_id in range(num_workers):
            thread = threading.Thread(target=worker_task, args=(worker_id, results))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=15)  # 15 second timeout

        # Verify all workers completed successfully
        assert all(results), f"Some database workers failed: {results}"

        # Verify sessions were properly isolated
        assert (
            len(session_manager.active_sessions) == 0
        ), "Some sessions were not properly closed"

        print(f"✅ Concurrent database operations test passed: {num_workers} threads")

    @pytest.mark.asyncio
    async def test_concurrent_resource_processor(self):
        """Test that ResourceProcessor handles concurrent resource processing safely."""
        session_manager = ThreadSafeSessionManager()

        # Mock LLM generator for testing
        from unittest.mock import AsyncMock

        mock_llm_generator = Mock()
        mock_llm_generator.generate_resource_description = AsyncMock(
            return_value="Test LLM description"
        )

        processor = ResourceProcessor(
            session_manager=session_manager, llm_generator=mock_llm_generator
        )

        # Create test resources
        resources = []
        for i in range(20):
            resources.append(
                {
                    "id": f"concurrent-resource-{i}",
                    "name": f"Concurrent Test Resource {i}",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "resource_group": f"rg-concurrent-{i}",
                    "subscription_id": f"sub-concurrent-{i}",
                }
            )

        # Process resources with multiple workers
        try:
            stats = await processor.process_resources(resources, max_workers=5)
        except Exception as e:
            print(f"Exception during process_resources: {e}")
            import traceback

            traceback.print_exc()
            raise

        # Verify processing completed successfully
        print(
            f"Stats: total={getattr(stats, 'total_resources', None)}, processed={getattr(stats, 'processed', None)}"
        )
        assert (
            stats.total_resources == 20
        ), f"Expected 20 total_resources, got {getattr(stats, 'total_resources', None)}"
        assert (
            stats.processed == 20
        ), f"Expected 20 processed, got {getattr(stats, 'processed', None)}"
        # Note: In our mock setup, all resources will be "successful" since we're not simulating failures

        # Verify session isolation
        thread_sessions = {}
        for log_entry in session_manager.access_log:
            if log_entry["action"] == "query_executed":
                thread_id = log_entry["thread_id"]
                session_id = log_entry["session_id"]

                if thread_id not in thread_sessions:
                    thread_sessions[thread_id] = set()
                thread_sessions[thread_id].add(session_id)

        print(f"Thread sessions used: {thread_sessions}")
        print(f"Number of threads used: {len(thread_sessions)}")
        # Should have used multiple threads and sessions
        assert (
            len(thread_sessions) > 1
        ), f"ResourceProcessor should use multiple threads, got {len(thread_sessions)}"

        print(
            f"✅ Concurrent ResourceProcessor test passed: {len(thread_sessions)} threads used"
        )

    def test_session_manager_stress_test(self):
        """Stress test the session manager with high concurrent load."""
        session_manager = ThreadSafeSessionManager()

        def stress_worker(worker_id: int, results: List[int]):
            """Worker that rapidly creates and closes sessions."""
            operations = 0
            try:
                for _i in range(50):
                    with session_manager.session() as session:
                        # Simulate rapid database operations
                        session.run("MATCH (n) RETURN count(n)")
                        operations += 1
                        # Very small delay to increase contention
                        time.sleep(0.0001)

                results[worker_id] = operations
            except Exception as e:
                print(f"Stress worker {worker_id} failed: {e}")
                results[worker_id] = -1

        # Run high number of concurrent workers
        num_workers = 20
        results = [0] * num_workers
        threads = []

        start_time = time.time()

        for worker_id in range(num_workers):
            thread = threading.Thread(target=stress_worker, args=(worker_id, results))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=30)  # 30 second timeout

        end_time = time.time()

        # Verify all workers completed successfully
        assert all(r > 0 for r in results), f"Some stress workers failed: {results}"

        # Verify no sessions leaked
        assert (
            len(session_manager.active_sessions) == 0
        ), "Sessions were not properly cleaned up"

        total_operations = sum(results)
        duration = end_time - start_time

        print(
            f"✅ Stress test passed: {num_workers} workers, {total_operations} operations in {duration:.2f}s"
        )
        print(f"   Rate: {total_operations/duration:.1f} operations/second")


def test_session_isolation_with_mock_neo4j_session_manager():
    """Test using a more realistic mock of Neo4jSessionManager."""

    class MockNeo4jSessionManager:
        """More realistic mock that simulates the actual Neo4jSessionManager behavior."""

        def __init__(self):
            self.sessions_created = 0
            self.active_sessions = set()
            self.lock = threading.Lock()

        def session(self):
            return MockSessionContext(self)

    class MockSessionContext:
        def __init__(self, manager: Any) -> None:
            self.manager = manager
            self.session_id = None

        def __enter__(self):
            with self.manager.lock:
                self.manager.sessions_created += 1
                self.session_id = self.manager.sessions_created
                self.manager.active_sessions.add(self.session_id)
            print(
                f"[DEBUG] Session {self.session_id} created. Active: {self.manager.active_sessions}"
            )
            return MockSession(self.session_id)

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            with self.manager.lock:
                self.manager.active_sessions.discard(self.session_id)
            print(
                f"[DEBUG] Session {self.session_id} closed. Remaining: {self.manager.active_sessions}"
            )

    class MockSession:
        def __init__(self, session_id: int) -> None:
            self.session_id = session_id

        def run(self, query: str, **params: Any) -> Mock:
            # Simulate work and potential contention issues
            time.sleep(0.001)
            mock_result = Mock()
            mock_result.single.return_value = {
                "count": 1,
                "session_id": self.session_id,
            }
            return mock_result

    try:
        # Test that our refactored classes work with this realistic mock
        session_manager = MockNeo4jSessionManager()

        # Test ResourceState
        print("[DEBUG] Testing ResourceState.resource_exists")
        resource_state = ResourceState(session_manager)
        result1 = resource_state.resource_exists("test-resource")
        print(f"[DEBUG] resource_exists returned: {result1}")
        assert result1

        # Test DatabaseOperations
        print("[DEBUG] Testing DatabaseOperations.upsert_resource")
        db_ops = DatabaseOperations(session_manager)
        test_resource = {
            "id": "test-id",
            "name": "Test Resource",
            "type": "Microsoft.Test/resource",
            "location": "eastus",
            "resource_group": "test-rg",
            "subscription_id": "test-sub",
        }
        result2 = db_ops.upsert_resource(test_resource)
        print(f"[DEBUG] upsert_resource returned: {result2}")
        assert result2

        # Verify all sessions were properly closed
        print(f"[DEBUG] Active sessions after tests: {session_manager.active_sessions}")
        assert len(session_manager.active_sessions) == 0, "Sessions leaked"
        assert session_manager.sessions_created > 0, "No sessions were created"

        print(
            f"✅ Session isolation test passed: {session_manager.sessions_created} sessions created and cleaned up"
        )
    except Exception as e:
        print(
            f"[ERROR] Exception in test_session_isolation_with_mock_neo4j_session_manager: {e}"
        )
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    # Run the tests directly for quick verification
    test = TestConcurrentDatabaseAccess()

    print("Running concurrent database access tests...")

    test.test_concurrent_resource_state_operations()
    test.test_concurrent_database_operations()

    print("Running stress test...")
    test.test_session_manager_stress_test()

    print("Running session isolation test...")
    test_session_isolation_with_mock_neo4j_session_manager()

    print("\n🎉 All concurrent access tests passed!")
