"""Configuration models for the Agentic Testing System."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class CLIConfig:
    """CLI testing configuration."""

    base_command: List[str] = field(default_factory=lambda: ["uv", "run", "atg"])
    timeout: int = 300  # seconds
    env_vars: Dict[str, str] = field(default_factory=dict)
    working_dir: str = "."
    capture_ansi: bool = True


@dataclass
class UIConfig:
    """UI testing configuration."""

    app_path: str = "spa/main/index.js"
    screenshot_dir: str = "outputs/screenshots"
    video_dir: str = "outputs/videos"
    viewport: Dict[str, int] = field(
        default_factory=lambda: {"width": 1920, "height": 1080}
    )
    headless: bool = False  # Run with UI visible for debugging
    slow_mo: int = 0  # Milliseconds to slow down operations for debugging
    timeout: int = 30000  # Default timeout for UI operations in ms


@dataclass
class LLMConfig:
    """LLM configuration for comprehension and analysis."""

    provider: str = "azure"  # or "openai"
    deployment: Optional[str] = None
    api_key: Optional[str] = None
    api_version: str = "2024-02-01"
    endpoint: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4000
    model: str = "gpt-4"

    def __post_init__(self):
        """Load from environment if not provided."""
        if self.provider == "azure":
            self.deployment = self.deployment or os.environ.get(
                "AZURE_OPENAI_DEPLOYMENT"
            )
            self.api_key = self.api_key or os.environ.get("AZURE_OPENAI_KEY")
            self.endpoint = self.endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        else:
            self.api_key = self.api_key or os.environ.get("OPENAI_API_KEY")


@dataclass
class GitHubConfig:
    """GitHub integration configuration."""

    repository: str = "rysweet/azure-tenant-grapher"
    create_issues: bool = True
    issue_labels: List[str] = field(default_factory=lambda: ["bug", "agentic-test"])
    assign_to: Optional[str] = None
    use_gh_cli: bool = True  # Use authenticated gh CLI


@dataclass
class PriorityConfig:
    """Issue prioritization configuration."""

    impact_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "critical_path": 1.0,
            "security": 0.9,
            "data_loss": 0.9,
            "frequency": 0.5,
            "ux": 0.3,
        }
    )
    auto_prioritize: bool = True


@dataclass
class ExecutionConfig:
    """Test execution configuration."""

    parallel_workers: int = 4
    retry_count: int = 3
    retry_backoff: float = 2.0  # Exponential backoff multiplier
    fail_fast: bool = False  # Stop on first failure
    test_suites: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "smoke": ["cli_basic", "ui_navigation"],
            "full": ["*"],
            "regression": ["cli_*", "ui_*", "integration_*"],
        }
    )
    cache_ttl: int = 3600  # Cache time-to-live in seconds


@dataclass
class TestConfig:
    """Main configuration for the testing system."""

    cli_config: CLIConfig = field(default_factory=CLIConfig)
    ui_config: UIConfig = field(default_factory=UIConfig)
    llm_config: LLMConfig = field(default_factory=LLMConfig)
    github_config: GitHubConfig = field(default_factory=GitHubConfig)
    priority_config: PriorityConfig = field(default_factory=PriorityConfig)
    execution_config: ExecutionConfig = field(default_factory=ExecutionConfig)

    # Test environment
    azure_tenant_id: Optional[str] = None
    azure_client_id: Optional[str] = None
    azure_client_secret: Optional[str] = None
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: Optional[str] = None

    # Logging
    log_level: str = "INFO"
    log_file: str = "outputs/logs/agentic_testing.log"

    def __post_init__(self):
        """Load Azure and Neo4j credentials from environment."""
        self.azure_tenant_id = self.azure_tenant_id or os.environ.get("AZURE_TENANT_ID")
        self.azure_client_id = self.azure_client_id or os.environ.get("AZURE_CLIENT_ID")
        self.azure_client_secret = self.azure_client_secret or os.environ.get(
            "AZURE_CLIENT_SECRET"
        )
        self.neo4j_password = self.neo4j_password or os.environ.get("NEO4J_PASSWORD")
        self.neo4j_uri = os.environ.get("NEO4J_URI", self.neo4j_uri)

    @classmethod
    def from_yaml(cls, path: str) -> "TestConfig":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        # Create nested configs
        config = cls()

        if "cli" in data:
            config.cli_config = CLIConfig(**data["cli"])
        if "ui" in data:
            config.ui_config = UIConfig(**data["ui"])
        if "llm" in data:
            config.llm_config = LLMConfig(**data["llm"])
        if "github" in data:
            config.github_config = GitHubConfig(**data["github"])
        if "priority" in data:
            config.priority_config = PriorityConfig(**data["priority"])
        if "execution" in data:
            config.execution_config = ExecutionConfig(**data["execution"])

        # Load top-level configs
        for key in [
            "azure_tenant_id",
            "azure_client_id",
            "neo4j_uri",
            "neo4j_user",
            "log_level",
            "log_file",
        ]:
            if key in data:
                setattr(config, key, data[key])

        return config

    def to_yaml(self, path: str):
        """Save configuration to YAML file."""
        data = {
            "cli": self.cli_config.__dict__,
            "ui": self.ui_config.__dict__,
            "llm": self.llm_config.__dict__,
            "github": self.github_config.__dict__,
            "priority": self.priority_config.__dict__,
            "execution": self.execution_config.__dict__,
            "azure_tenant_id": self.azure_tenant_id,
            "azure_client_id": self.azure_client_id,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "log_level": self.log_level,
            "log_file": self.log_file,
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
