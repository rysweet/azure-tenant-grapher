# mypy: disable-error-code=misc,no-untyped-def
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

from src.llm_descriptions import ThrottlingError
from src.resource_processor import (
    DatabaseOperations,
    ProcessingStats,
    ResourceProcessor,
    ResourceState,
    create_resource_processor,
    serialize_value,
)


class DummyAzureObject:
    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f"DummyAzureObject({self.name})"


class TestSerializeValue:
    def test_primitive_types(self):
        assert serialize_value("foo") == "foo"
        assert serialize_value(123) == 123
        assert serialize_value(3.14) == 3.14
        assert serialize_value(True) is True
        assert serialize_value(None) is None

    def test_list_of_primitives(self):
        assert serialize_value([1, "a", False]) == [1, "a", False]

    def test_dict(self):
        d = {"a": 1, "b": "x"}
        result = serialize_value(d)
        assert isinstance(result, str)
        assert '"a": 1' in result and '"b": "x"' in result

    def test_empty_dict(self):
        assert serialize_value({}) is None

    def test_sdk_object_with_name(self):
        obj = DummyAzureObject("sku-name")
        assert serialize_value(obj) == "sku-name"

    def test_object_without_name(self):
        class NoName:
            def __str__(self):
                return "custom"

        obj = NoName()
        assert serialize_value(obj) == "custom"

    def test_large_dict_truncation(self):
        d = {str(i): i for i in range(100)}
        s = serialize_value(d, max_json_length=100)
        assert s.endswith("...(truncated)")

    def test_list_of_mixed(self):
        obj = DummyAzureObject("sku")
        data = [1, {"x": 2}, obj, None]
        out = serialize_value(data)
        assert out[0] == 1
        assert isinstance(out[1], str)
        assert out[2] == "sku"
        assert out[3] is None


class TestProcessingStats:
    """Test cases for ProcessingStats."""

    def test_default_values(self) -> None:
        """Test default values for ProcessingStats."""
        stats = ProcessingStats()
        assert stats.total_resources == 0
        assert stats.processed == 0
        assert stats.successful == 0
        assert stats.failed == 0
        assert stats.skipped == 0
        assert stats.llm_generated == 0
        assert stats.llm_skipped == 0

    def test_success_rate_calculation(self) -> None:
        """Test success rate calculation."""
        stats = ProcessingStats()
        stats.processed = 10
        stats.successful = 8
        assert stats.success_rate == 80.0

        # Test division by zero protection
        stats.processed = 0
        stats.successful = 0  # Reset successful to 0 as well
        assert stats.success_rate == 0.0

    def test_progress_percentage_calculation(self) -> None:
        """Test progress percentage calculation."""
        stats = ProcessingStats()
        stats.total_resources = 100
        stats.processed = 25
        assert stats.progress_percentage == 25.0

        # Test division by zero protection
        stats.total_resources = 0
        stats.processed = 0  # Reset processed to 0 as well
        assert stats.progress_percentage == 0.0

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        stats = ProcessingStats()
        stats.total_resources = 10
        stats.processed = 8
        stats.successful = 6
        stats.failed = 2
        stats.skipped = 1
        stats.llm_generated = 5
        stats.llm_skipped = 1

        result = stats.to_dict()

        assert result["total_resources"] == 10
        assert result["processed"] == 8
        assert result["successful"] == 6
        assert result["failed"] == 2
        assert result["skipped"] == 1
        assert result["llm_generated"] == 5
        assert result["llm_skipped"] == 1
        assert result["success_rate"] == 75.0
        assert result["progress_percentage"] == 80.0


class TestResourceState:
    """Test cases for ResourceState."""

    def test_resource_exists_true(self, mock_neo4j_session: Mock) -> None:
        """Test resource_exists returns True when resource exists."""

        # Override the default behavior for this specific test
        def mock_run_with_count(*args: Any, **kwargs: Any) -> None:
            mock_record = Mock()
            mock_record.__getitem__ = Mock(return_value=1)  # count = 1
            mock_record.get = Mock(return_value=1)
            mock_record.keys = Mock(return_value=["count"])
            result = Mock()
            result.single.return_value = mock_record
            return result  # type: ignore[return-value]

        mock_neo4j_session.run.side_effect = mock_run_with_count

        state = ResourceState(mock_neo4j_session)
        result = state.resource_exists("test-resource-id")

        assert result is True
        mock_neo4j_session.run.assert_called_once()

    def test_resource_exists_false(self, mock_neo4j_session: Mock) -> None:
        """Test resource_exists returns False when resource doesn't exist."""
        mock_neo4j_session.run.return_value.single.return_value = {"count": 0}

        state = ResourceState(mock_neo4j_session)
        result = state.resource_exists("test-resource-id")

        assert result is False

    def test_resource_exists_exception(self, mock_neo4j_session: Mock) -> None:
        """Test resource_exists handles exceptions gracefully."""
        mock_neo4j_session.run.side_effect = Exception("Database error")

        state = ResourceState(mock_neo4j_session)
        result = state.resource_exists("test-resource-id")

        assert result is False

    def test_has_llm_description_true(self, mock_neo4j_session: Mock) -> None:
        """Test has_llm_description returns True when description exists."""

        # Override the default behavior for this specific test
        def mock_run_with_desc(*args: Any, **kwargs: Any) -> None:
            mock_record = Mock()
            mock_record.__getitem__ = Mock(return_value="A detailed description")
            mock_record.get = Mock(return_value="A detailed description")
            mock_record.keys = Mock(return_value=["desc"])
            result = Mock()
            result.single.return_value = mock_record
            return result  # type: ignore[return-value]

        mock_neo4j_session.run.side_effect = mock_run_with_desc

        state = ResourceState(mock_neo4j_session)
        result = state.has_llm_description("test-resource-id")

        assert result is True

    def test_has_llm_description_false_empty(self, mock_neo4j_session: Mock) -> None:
        """Test has_llm_description returns False for empty description."""
        mock_neo4j_session.run.return_value.single.return_value = {"desc": ""}

        state = ResourceState(mock_neo4j_session)
        result = state.has_llm_description("test-resource-id")

        assert result is False

    def test_has_llm_description_false_generic(self, mock_neo4j_session: Mock) -> None:
        """Test has_llm_description returns False for generic Azure description."""
        mock_neo4j_session.run.return_value.single.return_value = {
            "desc": "Azure Virtual Machine resource."
        }

        state = ResourceState(mock_neo4j_session)
        result = state.has_llm_description("test-resource-id")

        assert result is False

    def test_get_processing_metadata(self, mock_neo4j_session: Mock) -> None:
        """Test get_processing_metadata returns metadata."""

        # Override the default behavior for this specific test
        def mock_run_with_metadata(*args: Any, **kwargs: Any) -> None:
            mock_record = Mock()
            # Set up a proper dict-like object that supports both __getitem__ and keys()
            metadata = {
                "updated_at": "2023-01-01T00:00:00Z",
                "llm_description": "Test description",
                "processing_status": "completed",
            }
            mock_record.__getitem__ = Mock(side_effect=lambda key: metadata[key])
            mock_record.get = Mock(
                side_effect=lambda key, default=None: metadata.get(key, default)
            )
            mock_record.keys = Mock(return_value=list(metadata.keys()))
            result = Mock()
            result.single.return_value = mock_record
            return result  # type: ignore[return-value]

        mock_neo4j_session.run.side_effect = mock_run_with_metadata

        state = ResourceState(mock_neo4j_session)
        result = state.get_processing_metadata("test-resource-id")

        assert result["processing_status"] == "completed"
        assert result["updated_at"] == "2023-01-01T00:00:00Z"
        assert result["llm_description"] == "Test description"


class TestDatabaseOperations:
    """Test cases for DatabaseOperations."""

    def test_upsert_resource_success(
        self, mock_neo4j_session: Mock, sample_resource: Dict[str, Any]
    ) -> None:
        """Test successful resource upsert."""

        # Override the default behavior for this specific test
        def mock_run_success(query: Any, parameters: Any = None, **kwargs: Any) -> None:
            # Track the query
            mock_neo4j_session.queries_run.append(
                {"query": query, "params": parameters}
            )
            # For MERGE queries, just return a success mock
            result = Mock()
            result.single.return_value = {}
            return result  # type: ignore[return-value]

        mock_neo4j_session.run.side_effect = mock_run_success

        db_ops = DatabaseOperations(mock_neo4j_session)
        result = db_ops.upsert_resource(sample_resource, "completed")

        assert result is True
        assert len(mock_neo4j_session.queries_run) == 1
        query = mock_neo4j_session.queries_run[0]["query"]
        assert "MERGE (r:Resource {id: $id})" in query
        assert "processing_status" in query

    def test_upsert_resource_exception(
        self, mock_neo4j_session: Mock, sample_resource: Dict[str, Any]
    ) -> None:
        """Test resource upsert handles exceptions."""
        mock_neo4j_session.run.side_effect = Exception("Database error")

        db_ops = DatabaseOperations(mock_neo4j_session)
        result = db_ops.upsert_resource(sample_resource, "failed")

        assert result is False

    def test_create_subscription_relationship_success(
        self, mock_neo4j_session: Mock
    ) -> None:
        """Test successful subscription relationship creation."""

        # Override the default behavior for this specific test
        def mock_run_success(*args: Any, **kwargs: Any) -> None:
            result = Mock()
            result.single.return_value = {}
            return result  # type: ignore[return-value]

        mock_neo4j_session.run.side_effect = mock_run_success

        db_ops = DatabaseOperations(mock_neo4j_session)
        result = db_ops.create_subscription_relationship("sub-id", "resource-id")

        assert result is True

    def test_create_resource_group_relationships_success(
        self, mock_neo4j_session: Mock, sample_resource: Dict[str, Any]
    ) -> None:
        """Test successful resource group relationship creation."""

        # Override the default behavior for this specific test
        def mock_run_success(*args: Any, **kwargs: Any) -> None:
            result = Mock()
            result.single.return_value = {}
            return result  # type: ignore[return-value]

        mock_neo4j_session.run.side_effect = mock_run_success

        db_ops = DatabaseOperations(mock_neo4j_session)
        result = db_ops.create_resource_group_relationships(sample_resource)

        assert result is True

    def test_create_resource_group_relationships_no_rg(
        self, mock_neo4j_session: Mock, sample_resource: Dict[str, Any]
    ) -> None:
        """Test resource group relationships when no resource group."""
        resource_no_rg = sample_resource.copy()
        resource_no_rg["resource_group"] = None

        db_ops = DatabaseOperations(mock_neo4j_session)
        result = db_ops.create_resource_group_relationships(resource_no_rg)

        assert result is True
        assert len(mock_neo4j_session.queries_run) == 0


class TestResourceProcessor:
    """Test cases for ResourceProcessor."""

    def test_initialization(
        self, mock_neo4j_session: Mock, mock_llm_generator: Mock
    ) -> None:
        """Test ResourceProcessor initialization."""
        processor = ResourceProcessor(
            session=mock_neo4j_session,
            llm_generator=mock_llm_generator,
            resource_limit=100,
        )

        assert processor.session == mock_neo4j_session
        assert processor.llm_generator == mock_llm_generator
        assert processor.resource_limit == 100
        assert processor.stats.total_resources == 0

    def test_should_process_resource_new(
        self, mock_neo4j_session: Mock, sample_resource: Dict[str, Any]
    ) -> None:
        """Test should_process_resource for new resource."""
        # Mock resource doesn't exist
        mock_neo4j_session.run.return_value.single.return_value = {"count": 0}

        processor = ResourceProcessor(mock_neo4j_session)
        should_process, reason = processor._should_process_resource(sample_resource)

        assert should_process is True
        assert reason == "new_resource"

    def test_should_process_resource_needs_llm(
        self,
        mock_neo4j_session: Mock,
        sample_resource: Dict[str, Any],
        mock_llm_generator: Mock,
    ) -> None:
        """Test should_process_resource for resource needing LLM description."""
        # Mock resource exists but no LLM description
        mock_neo4j_session.run.side_effect = [
            Mock(single=lambda: {"count": 1}),  # resource_exists
            Mock(single=lambda: {"desc": None}),  # has_llm_description
        ]

        processor = ResourceProcessor(mock_neo4j_session, mock_llm_generator)
        should_process, reason = processor._should_process_resource(sample_resource)

        assert should_process is True
        assert reason == "needs_llm_description"

    def test_should_process_resource_already_processed(
        self, mock_neo4j_session: Mock, sample_resource: Dict[str, Any]
    ) -> None:
        """Test should_process_resource for already processed resource."""
        # Mock resource exists with LLM description
        mock_neo4j_session.run.side_effect = [
            Mock(single=lambda: {"count": 1}),  # resource_exists
            Mock(
                single=lambda: {"desc": "Detailed description"}
            ),  # has_llm_description
            Mock(
                single=lambda: {"processing_status": "completed"}
            ),  # get_processing_metadata
        ]

        processor = ResourceProcessor(mock_neo4j_session)
        should_process, reason = processor._should_process_resource(sample_resource)

        assert should_process is False
        assert reason == "already_processed"

    @pytest.mark.asyncio
    async def test_process_single_resource_llm_success(
        self,
        mock_neo4j_session: Mock,
        sample_resource: Dict[str, Any],
        mock_llm_generator: Mock,
    ) -> None:
        """Test successful LLM description generation for single resource."""
        processor = ResourceProcessor(mock_neo4j_session, mock_llm_generator)
        success, description = await processor._process_single_resource_llm(
            sample_resource
        )

        assert success is True
        assert "Mock description" in description
        assert len(mock_llm_generator.descriptions_generated) == 1

    @pytest.mark.asyncio
    async def test_process_single_resource_llm_no_generator(
        self, mock_neo4j_session: Mock, sample_resource: Dict[str, Any]
    ) -> None:
        """Test LLM description generation when no generator available."""
        processor = ResourceProcessor(mock_neo4j_session)
        success, description = await processor._process_single_resource_llm(
            sample_resource
        )

        assert success is False
        assert "Azure" in description

    @pytest.mark.asyncio
    async def test_process_single_resource_success(
        self,
        mock_neo4j_session: Mock,
        sample_resource: Dict[str, Any],
        mock_llm_generator: Mock,
    ) -> None:
        """Test successful processing of single resource."""
        # Mock resource doesn't exist (new resource)
        mock_neo4j_session.run.return_value.single.return_value = {"count": 0}

        processor = ResourceProcessor(mock_neo4j_session, mock_llm_generator)
        result = await processor.process_single_resource(sample_resource, 0)

        assert result is True
        assert processor.stats.processed == 1
        assert processor.stats.successful == 1
        assert processor.stats.llm_generated == 1

    @pytest.mark.asyncio
    async def test_process_single_resource_skip(
        self, mock_neo4j_session: Mock, sample_resource: Dict[str, Any]
    ) -> None:
        """Test skipping already processed resource."""
        # Update the resource to have a proper LLM description that won't trigger reprocessing
        sample_resource["llm_description"] = (
            "This is a detailed virtual machine description generated by LLM"
        )

        # Create a custom mock function that handles each query type correctly
        call_count = 0

        def custom_mock_run(query: Any, parameters: Any = None, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1

            result = Mock()

            if call_count == 1:  # First call - upsert_resource (processing status)
                result.single.return_value = {}
                return result  # type: ignore[return-value]
            elif call_count == 2:  # Second call - resource_exists
                mock_record = Mock()
                mock_record.__getitem__ = Mock(return_value=1)  # count = 1 (exists)
                mock_record.get = Mock(return_value=1)
                result.single.return_value = mock_record
                return result  # type: ignore[return-value]
            elif call_count == 3:  # Third call - has_llm_description
                mock_record = Mock()
                mock_record.__getitem__ = Mock(
                    return_value="This is a detailed virtual machine description generated by LLM"
                )
                mock_record.get = Mock(
                    return_value="This is a detailed virtual machine description generated by LLM"
                )
                result.single.return_value = mock_record
                return result  # type: ignore[return-value]
            elif call_count == 4:  # Fourth call - get_processing_metadata
                mock_record = Mock()
                mock_record.__getitem__ = Mock(
                    side_effect=lambda key: {
                        "processing_status": "completed",
                        "updated_at": "2023-01-01T00:00:00Z",
                        "llm_description": "This is a detailed virtual machine description generated by LLM",
                    }.get(key)
                )
                mock_record.get = Mock(
                    side_effect=lambda key, default=None: {
                        "processing_status": "completed",
                        "updated_at": "2023-01-01T00:00:00Z",
                        "llm_description": "This is a detailed virtual machine description generated by LLM",
                    }.get(key, default)
                )
                result.single.return_value = mock_record
                return result  # type: ignore[return-value]
            else:
                # Any additional calls
                result.single.return_value = {}
                return result  # type: ignore[return-value]

        mock_neo4j_session.run.side_effect = custom_mock_run

        processor = ResourceProcessor(mock_neo4j_session)
        result = await processor.process_single_resource(sample_resource, 0)

        assert result is True
        assert processor.stats.processed == 1
        assert processor.stats.skipped == 1

    @pytest.mark.asyncio
    async def test_process_resources_batch_empty(
        self, mock_neo4j_session: Mock
    ) -> None:
        """Test processing empty resource list."""
        processor = ResourceProcessor(mock_neo4j_session)
        stats = await processor.process_resources_batch([])

        assert stats.total_resources == 0
        assert stats.processed == 0

    @pytest.mark.asyncio
    async def test_process_resources_batch_with_limit(
        self, mock_neo4j_session: Mock, sample_resources: List[Any]
    ) -> None:
        """Test processing resources with limit."""
        # Mock all resources as new
        mock_neo4j_session.run.return_value.single.return_value = {"count": 0}

        processor = ResourceProcessor(mock_neo4j_session, resource_limit=1)
        stats = await processor.process_resources_batch(sample_resources, batch_size=1)

        assert stats.total_resources == 1  # Limited to 1
        assert stats.processed == 1

    @pytest.mark.asyncio
    async def test_process_resources_batch_parallel(
        self,
        mock_neo4j_session: Mock,
        sample_resources: List[Any],
        mock_llm_generator: Mock,
    ) -> None:
        """Test parallel processing of resources."""
        # Mock all resources as new
        mock_neo4j_session.run.return_value.single.return_value = {"count": 0}

        processor = ResourceProcessor(mock_neo4j_session, mock_llm_generator)
        stats = await processor.process_resources_batch(sample_resources, batch_size=2)

        assert stats.total_resources == 2
        assert stats.processed == 2
        assert stats.successful == 2
        assert stats.llm_generated == 2


class TestFactoryFunction:
    """Test cases for factory function."""

    def test_create_resource_processor(
        self, mock_neo4j_session: Mock, mock_llm_generator: Mock
    ) -> None:
        """Test resource processor factory function."""
        processor = create_resource_processor(
            session=mock_neo4j_session,
            llm_generator=mock_llm_generator,
            resource_limit=50,
        )

        assert isinstance(processor, ResourceProcessor)
        assert processor.session == mock_neo4j_session
        assert processor.llm_generator == mock_llm_generator


class DummyLLMGenerator:
    def __init__(self, throttle_on=2, success_after=5):
        self.call_count = 0
        self.throttle_on = throttle_on
        self.success_after = success_after

    def generate_resource_description(self, resource):
        self.call_count += 1
        if self.call_count == self.throttle_on:
            raise ThrottlingError("Simulated throttling")
        if self.call_count < self.success_after:
            return f"desc-{self.call_count}"
        return "desc-final"


def test_async_llm_summary_pool_throttling_and_counters():
    from src.resource_processor import process_resources_async_llm

    # Prepare dummy resources
    resources = [
        {"id": f"r{i}", "subscription_id": "sub", "resource_group": "rg"}
        for i in range(5)
    ]
    counters = {
        "total": 0,
        "inserted": 0,
        "llm_generated": 0,
        "llm_skipped": 0,
        "in_flight": 0,
        "remaining": 0,
        "throttled": 0,
    }
    counters_lock = threading.Lock()
    llm_gen = DummyLLMGenerator(throttle_on=2, success_after=4)

    # Use a small pool to force throttling logic
    with ThreadPoolExecutor(max_workers=3) as executor:
        # session is not used in dummy insert_resource
        futures = process_resources_async_llm(
            session=None,
            resources=resources,
            llm_generator=llm_gen,
            summary_executor=executor,
            counters=counters,
            counters_lock=counters_lock,
            max_workers=3,
        )
        # Wait for all to complete
        for f in futures:
            try:
                f.result()
            except ThrottlingError:
                pass
            except Exception:
                pass

    # Check counters
    with counters_lock:
        assert counters["total"] == 5
        assert counters["inserted"] == 5
        assert counters["llm_generated"] + counters["llm_skipped"] == 5
        assert counters["remaining"] == 0
        assert counters["in_flight"] == 0
        assert counters["throttled"] >= 1
        # Removed invalid assertion: processor.resource_limit == 50
