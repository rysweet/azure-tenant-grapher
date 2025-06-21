"""
Tests for ResourceGroup and Tag LLM description generation.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.llm_descriptions import AzureLLMDescriptionGenerator
from src.resource_processor import ResourceProcessor


class TestResourceGroupTagLLM:
    """Test cases for ResourceGroup and Tag LLM description generation."""

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        session_manager = Mock()
        session = Mock()

        # Create a proper context manager mock
        context_manager = Mock()
        context_manager.__enter__ = Mock(return_value=session)
        context_manager.__exit__ = Mock(return_value=None)
        session_manager.session = Mock(return_value=context_manager)

        return session_manager, session

    @pytest.fixture
    def mock_llm_generator(self):
        """Create a mock LLM generator."""
        generator = Mock(spec=AzureLLMDescriptionGenerator)
        generator.generate_resource_group_description = AsyncMock(
            return_value="Test ResourceGroup description"
        )
        generator.generate_tag_description = AsyncMock(
            return_value="Test Tag description"
        )
        return generator

    @pytest.mark.asyncio
    async def test_generate_resource_group_summaries(
        self, mock_session_manager, mock_llm_generator
    ):
        """Test ResourceGroup summary generation."""
        session_manager, session = mock_session_manager

        # Mock ResourceGroups needing descriptions
        rg_result = Mock()
        rg_result.__iter__ = Mock(
            return_value=iter([{"name": "test-rg", "subscription_id": "sub-123"}])
        )

        # Mock resources in ResourceGroup
        resources_result = Mock()
        resources_result.__iter__ = Mock(
            return_value=iter(
                [
                    {
                        "name": "test-vm",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                        "id": "vm-123",
                    }
                ]
            )
        )

        session.run.side_effect = [rg_result, resources_result, Mock()]

        processor = ResourceProcessor(session_manager, mock_llm_generator)

        await processor.generate_resource_group_summaries()

        # Verify LLM generator was called
        mock_llm_generator.generate_resource_group_description.assert_called_once_with(
            "test-rg",
            "sub-123",
            [
                {
                    "name": "test-vm",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "id": "vm-123",
                }
            ],
        )

        # Verify database update was called
        assert session.run.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_tag_summaries(
        self, mock_session_manager, mock_llm_generator
    ):
        """Test Tag summary generation."""
        session_manager, session = mock_session_manager

        # Mock Tags needing descriptions
        tag_result = Mock()
        tag_result.__iter__ = Mock(
            return_value=iter(
                [
                    {
                        "id": "Environment:Production",
                        "key": "Environment",
                        "value": "Production",
                    }
                ]
            )
        )

        # Mock tagged resources
        tagged_resources_result = Mock()
        tagged_resources_result.__iter__ = Mock(
            return_value=iter(
                [
                    {
                        "name": "test-vm",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                        "resource_group": "test-rg",
                    }
                ]
            )
        )

        session.run.side_effect = [tag_result, tagged_resources_result, Mock()]

        processor = ResourceProcessor(session_manager, mock_llm_generator)

        await processor.generate_tag_summaries()

        # Verify LLM generator was called
        mock_llm_generator.generate_tag_description.assert_called_once_with(
            "Environment",
            "Production",
            [
                {
                    "name": "test-vm",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "resource_group": "test-rg",
                }
            ],
        )

        # Verify database update was called
        assert session.run.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_summaries_no_llm_generator(self, mock_session_manager):
        """Test that summary generation is skipped when no LLM generator is available."""
        session_manager, session = mock_session_manager

        processor = ResourceProcessor(session_manager, None)  # No LLM generator

        await processor.generate_resource_group_summaries()
        await processor.generate_tag_summaries()

        # Verify no database calls were made
        session.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_summaries_with_empty_results(
        self, mock_session_manager, mock_llm_generator
    ):
        """Test summary generation when no ResourceGroups or Tags need descriptions."""
        session_manager, session = mock_session_manager

        # Mock empty results
        empty_result = Mock()
        empty_result.__iter__ = Mock(return_value=iter([]))

        session.run.return_value = empty_result

        processor = ResourceProcessor(session_manager, mock_llm_generator)

        await processor.generate_resource_group_summaries()
        await processor.generate_tag_summaries()

        # Verify LLM generator was not called
        mock_llm_generator.generate_resource_group_description.assert_not_called()
        mock_llm_generator.generate_tag_description.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_summaries_handles_exceptions(
        self, mock_session_manager, mock_llm_generator
    ):
        """Test that exceptions during summary generation are handled gracefully."""
        session_manager, session = mock_session_manager

        # Mock database error
        session.run.side_effect = Exception("Database error")

        processor = ResourceProcessor(session_manager, mock_llm_generator)

        # Should not raise exception
        await processor.generate_resource_group_summaries()
        await processor.generate_tag_summaries()
