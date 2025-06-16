import asyncio
import logging
from typing import Callable, Optional

from src.config_manager import SpecificationConfig
from src.exceptions import TenantSpecificationError
from src.llm_descriptions import AzureLLMDescriptionGenerator
from src.tenant_spec_generator import ResourceAnonymizer, TenantSpecificationGenerator
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class TenantSpecificationService:
    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        llm_generator: Optional[AzureLLMDescriptionGenerator],
        config: SpecificationConfig,
        generator_factory: Optional[Callable[..., TenantSpecificationGenerator]] = None,
    ):
        self.session_manager = session_manager
        self.llm_generator = llm_generator
        self.config = config
        self.generator_factory = generator_factory

    async def generate_specification(self, output_path: str) -> str:
        def _generate() -> str:
            with self.session_manager as session:
                uri = getattr(session, "uri", None)
                user = getattr(session, "user", None)
                password = getattr(session, "password", None)
                if not (
                    isinstance(uri, str)
                    and isinstance(user, str)
                    and isinstance(password, str)
                ):
                    raise TenantSpecificationError(
                        "Neo4j session manager did not provide required credentials as strings."
                    )

                anonymizer = ResourceAnonymizer(
                    seed=self.config.anonymization_seed
                    if hasattr(self.config, "anonymization_seed")
                    else None
                )
                generator = (
                    self.generator_factory(uri, user, password, anonymizer, self.config)
                    if self.generator_factory
                    else TenantSpecificationGenerator(
                        uri, user, password, anonymizer, self.config
                    )
                )

                # Only markdown output is supported
                spec_path = generator.generate_specification(output_path)

                # LLM enrichment if enabled (stub)
                if self.llm_generator:
                    logger.info(
                        "LLM enrichment enabled, but enrichment logic is not implemented in this stub."
                    )

                return spec_path

        try:
            result = await asyncio.to_thread(_generate)
            return result
        except Exception as exc:
            logger.exception("Failed to generate tenant specification")
            raise TenantSpecificationError(
                "Failed to generate tenant specification.",
                output_path=output_path,
            ) from exc
