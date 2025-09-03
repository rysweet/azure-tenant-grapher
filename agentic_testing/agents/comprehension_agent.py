"""Comprehension agent for understanding features and generating test scenarios."""

import re
from pathlib import Path
from typing import Any, Dict, List

from ..config import LLMConfig
from ..models import (
    FeatureSpec,
    Priority,
    TestInterface,
    TestScenario,
    TestStep,
    VerificationStep,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DocumentationLoader:
    """Load and parse documentation files."""

    def __init__(self, docs_dir: str = "docs"):
        """
        Initialize documentation loader.

        Args:
            docs_dir: Directory containing documentation
        """
        self.docs_dir = Path(docs_dir)

    def load_markdown_files(self) -> Dict[str, str]:
        """
        Load all markdown documentation files.

        Returns:
            Dictionary of file paths to content
        """
        docs = {}

        for md_file in self.docs_dir.rglob("*.md"):
            try:
                with open(md_file, encoding="utf-8") as f:
                    docs[str(md_file)] = f.read()
                logger.debug(f"Loaded documentation: {md_file}")
            except Exception as e:
                logger.error(f"Failed to load {md_file}: {e}")

        return docs

    def extract_features(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract feature descriptions from documentation.

        Args:
            content: Documentation content

        Returns:
            List of feature dictionaries
        """
        features = []

        # Extract CLI commands
        cli_pattern = r"`atg\s+([a-z-]+)`|`azure-tenant-grapher\s+([a-z-]+)`"
        for match in re.finditer(cli_pattern, content):
            command = match.group(1) or match.group(2)
            features.append(
                {
                    "type": "cli",
                    "name": command,
                    "context": content[
                        max(0, match.start() - 200) : min(
                            len(content), match.end() + 200
                        )
                    ],
                }
            )

        # Extract UI features from headers
        header_pattern = r"^#{1,3}\s+(.+)$"
        for match in re.finditer(header_pattern, content, re.MULTILINE):
            header = match.group(1)
            if any(
                keyword in header.lower()
                for keyword in ["tab", "button", "page", "dialog", "menu"]
            ):
                features.append(
                    {
                        "type": "ui",
                        "name": header,
                        "context": content[
                            max(0, match.start() - 200) : min(
                                len(content), match.end() + 500
                            )
                        ],
                    }
                )

        return features


class ComprehensionAgent:
    """Agent for understanding features and generating test scenarios."""

    def __init__(self, config: LLMConfig):
        """
        Initialize comprehension agent.

        Args:
            config: LLM configuration
        """
        self.config = config
        self.doc_loader = DocumentationLoader()
        self._llm_client = None

    async def _get_llm_client(self):
        """Get or create LLM client."""
        if self._llm_client is None:
            if self.config.provider == "azure":
                from openai import AsyncAzureOpenAI

                self._llm_client = AsyncAzureOpenAI(
                    api_key=self.config.api_key,
                    api_version=self.config.api_version,
                    azure_endpoint=self.config.endpoint,
                    azure_deployment=self.config.deployment,
                )
            else:
                from openai import AsyncOpenAI

                self._llm_client = AsyncOpenAI(api_key=self.config.api_key)
        return self._llm_client

    async def analyze_feature(self, feature_doc: str) -> FeatureSpec:
        """
        Analyze a feature from documentation using LLM.

        Args:
            feature_doc: Feature documentation text

        Returns:
            FeatureSpec with extracted information
        """
        client = await self._get_llm_client()

        prompt = f"""Analyze this feature documentation and extract structured information.

Documentation:
{feature_doc}

Extract and return as JSON:
{{
    "name": "feature name",
    "purpose": "what the feature does",
    "inputs": [
        {{"name": "input1", "type": "string", "required": true, "description": "..."}}
    ],
    "outputs": [
        {{"name": "output1", "type": "object", "description": "..."}}
    ],
    "success_criteria": [
        "criterion 1",
        "criterion 2"
    ],
    "failure_modes": [
        "possible failure 1",
        "possible failure 2"
    ],
    "edge_cases": [
        "edge case 1",
        "edge case 2"
    ],
    "dependencies": ["dependency1", "dependency2"]
}}
"""

        try:
            response = await client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a test scenario generator. Extract structured information from documentation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            content = response.choices[0].message.content
            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                return FeatureSpec.from_llm_response(json_match.group())
            else:
                raise ValueError("No JSON found in LLM response")

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            # Return a basic spec
            return FeatureSpec(
                name="Unknown Feature",
                purpose="Feature purpose not determined",
                inputs=[],
                outputs=[],
                success_criteria=["Feature executes without error"],
                failure_modes=["Feature fails to execute"],
                edge_cases=[],
            )

    async def generate_test_scenarios(
        self, feature_spec: FeatureSpec
    ) -> List[TestScenario]:
        """
        Generate test scenarios from feature specification.

        Args:
            feature_spec: Feature specification

        Returns:
            List of test scenarios
        """
        scenarios = []
        scenario_id = 1

        # Generate success path scenario
        scenarios.append(
            TestScenario(
                id=f"{feature_spec.name.replace(' ', '_').lower()}_{scenario_id}",
                feature=feature_spec.name,
                name=f"{feature_spec.name} - Success Path",
                description=f"Verify {feature_spec.name} works correctly with valid inputs",
                interface=self._determine_interface(feature_spec.name),
                steps=self._generate_success_steps(feature_spec),
                expected_outcome="; ".join(feature_spec.success_criteria[:2])
                if feature_spec.success_criteria
                else "Feature executes successfully",
                verification=self._generate_verification_steps(feature_spec),
                tags=["success-path", "smoke-test"],
                priority=Priority.HIGH,
            )
        )
        scenario_id += 1

        # Generate failure mode scenarios
        for failure_mode in feature_spec.failure_modes[
            :3
        ]:  # Limit to 3 failure scenarios
            scenarios.append(
                TestScenario(
                    id=f"{feature_spec.name.replace(' ', '_').lower()}_{scenario_id}",
                    feature=feature_spec.name,
                    name=f"{feature_spec.name} - Failure: {failure_mode[:50]}",
                    description=f"Verify {feature_spec.name} handles failure: {failure_mode}",
                    interface=self._determine_interface(feature_spec.name),
                    steps=self._generate_failure_steps(feature_spec, failure_mode),
                    expected_outcome=f"Feature handles error gracefully: {failure_mode}",
                    verification=[
                        VerificationStep(
                            type="text",
                            target="error_message",
                            expected=failure_mode,
                            operator="contains",
                        )
                    ],
                    tags=["failure-mode", "error-handling"],
                    priority=Priority.MEDIUM,
                )
            )
            scenario_id += 1

        # Generate edge case scenarios
        for edge_case in feature_spec.edge_cases[:2]:  # Limit to 2 edge cases
            scenarios.append(
                TestScenario(
                    id=f"{feature_spec.name.replace(' ', '_').lower()}_{scenario_id}",
                    feature=feature_spec.name,
                    name=f"{feature_spec.name} - Edge Case: {edge_case[:50]}",
                    description=f"Verify {feature_spec.name} handles edge case: {edge_case}",
                    interface=self._determine_interface(feature_spec.name),
                    steps=self._generate_edge_case_steps(feature_spec, edge_case),
                    expected_outcome=f"Feature handles edge case correctly: {edge_case}",
                    verification=self._generate_verification_steps(feature_spec),
                    tags=["edge-case"],
                    priority=Priority.LOW,
                )
            )
            scenario_id += 1

        return scenarios

    def _determine_interface(self, feature_name: str) -> TestInterface:
        """Determine test interface based on feature name."""
        feature_lower = feature_name.lower()

        if any(
            cli_word in feature_lower
            for cli_word in ["command", "cli", "atg", "generate", "build"]
        ):
            return TestInterface.CLI
        elif any(
            ui_word in feature_lower
            for ui_word in ["tab", "button", "page", "ui", "spa", "electron"]
        ):
            return TestInterface.GUI
        elif "api" in feature_lower:
            return TestInterface.API
        else:
            return TestInterface.MIXED

    def _generate_success_steps(self, spec: FeatureSpec) -> List[TestStep]:
        """Generate success path test steps."""
        steps = []

        # Add setup step if dependencies exist
        if spec.dependencies:
            steps.append(
                TestStep(
                    action="execute",
                    target=f"setup {spec.dependencies[0]}",
                    description=f"Set up {spec.dependencies[0]}",
                )
            )

        # Add main execution step
        steps.append(
            TestStep(
                action="execute",
                target=spec.name.lower().replace(" ", "-"),
                description=f"Execute {spec.name}",
            )
        )

        # Add verification step
        steps.append(
            TestStep(
                action="verify",
                target="output",
                expected=spec.success_criteria[0]
                if spec.success_criteria
                else "Success",
                description="Verify successful execution",
            )
        )

        return steps

    def _generate_failure_steps(
        self, spec: FeatureSpec, failure_mode: str
    ) -> List[TestStep]:
        """Generate failure mode test steps."""
        return [
            TestStep(
                action="execute",
                target=spec.name.lower().replace(" ", "-"),
                value="invalid_input",  # Trigger failure
                description=f"Execute {spec.name} with invalid input",
            ),
            TestStep(
                action="verify",
                target="error",
                expected=failure_mode,
                description=f"Verify error handling for: {failure_mode}",
            ),
        ]

    def _generate_edge_case_steps(
        self, spec: FeatureSpec, edge_case: str
    ) -> List[TestStep]:
        """Generate edge case test steps."""
        return [
            TestStep(
                action="execute",
                target=spec.name.lower().replace(" ", "-"),
                value=edge_case,
                description=f"Execute {spec.name} with edge case: {edge_case}",
            ),
            TestStep(
                action="verify",
                target="output",
                expected="handled",
                description=f"Verify edge case handled: {edge_case}",
            ),
        ]

    def _generate_verification_steps(self, spec: FeatureSpec) -> List[VerificationStep]:
        """Generate verification steps."""
        steps = []

        for criterion in spec.success_criteria[:3]:  # Limit to 3 verification steps
            steps.append(
                VerificationStep(
                    type="text",
                    target="output",
                    expected=criterion,
                    operator="contains",
                    description=f"Verify: {criterion}",
                )
            )

        return steps

    async def discover_features(self) -> List[Dict[str, Any]]:
        """
        Discover features from documentation.

        Returns:
            List of discovered features
        """
        docs = self.doc_loader.load_markdown_files()
        all_features = []

        for doc_path, content in docs.items():
            features = self.doc_loader.extract_features(content)
            for feature in features:
                feature["source"] = doc_path
            all_features.extend(features)

        logger.info(f"Discovered {len(all_features)} features from documentation")
        return all_features
