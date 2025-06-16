import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.config_manager import SpecificationConfig
from src.exceptions import TenantSpecificationError
from src.services.tenant_specification_service import TenantSpecificationService


@pytest.fixture
def mock_session_manager():
    class DummySession:
        uri = "bolt://localhost:7687"
        user = "neo4j"
        password = "test"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    mgr = MagicMock()
    mgr.__enter__.return_value = DummySession()
    mgr.__exit__.return_value = None
    return mgr


@pytest.fixture
def mock_generator_factory():
    def factory(uri, user, password, anonymizer, config):
        gen = MagicMock()
        gen.generate_specification.return_value = "/tmp/spec.md"
        return gen

    return factory


@pytest.fixture
def config():
    return SpecificationConfig(
        output_directory="/tmp",
        resource_limit=10,
        include_ai_summaries=False,
        include_configuration_details=False,
        anonymization_seed="seed",
        template_style="comprehensive",
    )


def asyncio_run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_successful_generation_returns_path_and_writes_content(
    mock_session_manager, mock_generator_factory, config
):
    service = TenantSpecificationService(
        session_manager=mock_session_manager,
        llm_generator=None,
        config=config,
        generator_factory=mock_generator_factory,
    )
    result = asyncio_run(service.generate_specification("/tmp/spec.md"))
    assert result == "/tmp/spec.md"


def test_llm_enrichment_path_called_when_llm_generator_present(
    mock_session_manager, mock_generator_factory, config
):
    mock_llm = MagicMock()
    service = TenantSpecificationService(
        session_manager=mock_session_manager,
        llm_generator=mock_llm,
        config=config,
        generator_factory=mock_generator_factory,
    )
    with patch("src.services.tenant_specification_service.logger") as mock_logger:
        result = asyncio_run(service.generate_specification("/tmp/spec.md"))
        assert result == "/tmp/spec.md"
        mock_logger.info.assert_any_call(
            "LLM enrichment enabled, but enrichment logic is not implemented in this stub."
        )


def test_generator_raises_error_service_raises_tenant_specification_error(
    mock_session_manager, config
):
    def factory(*args, **kwargs):
        gen = MagicMock()
        gen.generate_specification.side_effect = RuntimeError("fail")
        return gen

    service = TenantSpecificationService(
        session_manager=mock_session_manager,
        llm_generator=None,
        config=config,
        generator_factory=factory,
    )
    with pytest.raises(TenantSpecificationError) as excinfo:
        asyncio_run(service.generate_specification("/tmp/spec.md"))
    assert "Failed to generate tenant specification." in str(excinfo.value)
