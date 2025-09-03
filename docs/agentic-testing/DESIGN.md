# Agentic Testing System - Design Document

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Orchestration Layer                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           ATGTestingOrchestrator                    │   │
│  │  - Test Planning & Scheduling                       │   │
│  │  - Agent Coordination                               │   │
│  │  - Progress Tracking                                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
      ┌───────────┬───────────┼───────────┬───────────┐
      ▼           ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│   CLI    │ │Electron  │ │Feature   │ │  Issue   │ │Priority  │
│  Agent   │ │UI Agent  │ │Comprehend│ │ Reporter │ │  Agent   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
      │           │           │           │           │
      └───────────┴───────────┴───────────┴───────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Infrastructure   │
                    │ - Playwright       │
                    │ - GitHub API       │
                    │ - Azure OpenAI     │
                    │ - Neo4j Driver     │
                    └───────────────────┘
```

### 1.2 Component Design

#### 1.2.1 Orchestrator Component
- **Technology**: Python with asyncio for concurrent operations
- **Responsibilities**: Coordinate agents, manage test lifecycle, track progress
- **Implementation**: Based on AutoGen framework patterns from Magentic-One

#### 1.2.2 Agent Components
- **CLI Agent**: Python subprocess with pexpect for interactive sessions
- **UI Agent**: TypeScript with Playwright Electron API
- **Comprehension Agent**: Python with LangChain and Azure OpenAI
- **Issue Reporter**: Python with PyGitHub library
- **Priority Agent**: Python with scikit-learn for classification

### 1.3 Data Flow

```
Documentation → Comprehension Agent → Test Scenarios
                                          ↓
Application → Test Agents → Test Results → Issue Detection
                                              ↓
                                        Issue Reporter → GitHub
```

## 2. Detailed Component Design

### 2.1 Orchestrator Design

```python
# agentic_testing/orchestrator.py

class ATGTestingOrchestrator:
    def __init__(self, config: TestConfig):
        self.config = config
        self.agents = self._initialize_agents()
        self.test_queue = asyncio.Queue()
        self.results_store = ResultsStore()
        self.state_manager = StateManager()

    async def run(self):
        """Main orchestration loop"""
        # Phase 1: Discovery
        features = await self._discover_features()

        # Phase 2: Comprehension
        scenarios = await self._generate_scenarios(features)

        # Phase 3: Execution
        results = await self._execute_tests(scenarios)

        # Phase 4: Reporting
        await self._report_issues(results)

    def _initialize_agents(self):
        return {
            'cli': CLIAgent(self.config.cli_config),
            'ui': ElectronUIAgent(self.config.ui_config),
            'comprehension': ComprehensionAgent(self.config.llm_config),
            'reporter': IssueReporter(self.config.github_config),
            'prioritizer': PriorityAgent(self.config.priority_config)
        }
```

### 2.2 CLI Agent Design

```python
# agentic_testing/agents/cli_agent.py

class CLIAgent:
    def __init__(self, config: CLIConfig):
        self.base_command = ['uv', 'run', 'atg']
        self.env = self._setup_environment(config)
        self.timeout = config.timeout

    async def execute_command(self, command: str, args: List[str]) -> CommandResult:
        """Execute a CLI command and capture output"""
        proc = await asyncio.create_subprocess_exec(
            *self.base_command, command, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=self.timeout
        )

        return CommandResult(
            command=command,
            args=args,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
            returncode=proc.returncode,
            duration=self._measure_duration()
        )

    async def interactive_session(self, command: str) -> InteractiveSession:
        """Start an interactive CLI session using pexpect"""
        import pexpect

        session = pexpect.spawn(
            ' '.join([*self.base_command, command]),
            env=self.env,
            encoding='utf-8'
        )

        return InteractiveSession(session)
```

### 2.3 Electron UI Agent Design

```typescript
// agentic_testing/agents/electron_ui_agent.ts

import { _electron as electron, ElectronApplication, Page } from 'playwright';

export class ElectronUIAgent {
    private app: ElectronApplication | null = null;
    private page: Page | null = null;
    private screenshotDir: string;

    constructor(config: UIConfig) {
        this.screenshotDir = config.screenshotDir;
    }

    async launch(): Promise<void> {
        this.app = await electron.launch({
            args: ['spa/main/index.js'],
            env: {
                ...process.env,
                NODE_ENV: 'test',
                TESTING_MODE: 'true'
            }
        });

        this.page = await this.app.firstWindow();

        // Wait for app to be ready
        await this.page.waitForSelector('[data-testid="app-ready"]', {
            timeout: 30000
        });
    }

    async clickTab(tabName: string): Promise<void> {
        const tabSelector = `[role="tab"][aria-label="${tabName}"]`;
        await this.page!.click(tabSelector);
        await this.page!.waitForLoadState('networkidle');
    }

    async fillInput(label: string, value: string): Promise<void> {
        // Use accessible selectors
        const input = await this.page!.getByLabel(label);
        await input.fill(value);
    }

    async captureState(): Promise<AppState> {
        const screenshot = await this.page!.screenshot({
            path: `${this.screenshotDir}/${Date.now()}.png`,
            fullPage: true
        });

        const accessibility = await this.page!.accessibility.snapshot();

        return {
            screenshot,
            accessibility,
            url: this.page!.url(),
            title: await this.page!.title()
        };
    }
}
```

### 2.4 Feature Comprehension Agent Design

```python
# agentic_testing/agents/comprehension_agent.py

from langchain.chat_models import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser

class ComprehensionAgent:
    def __init__(self, config: LLMConfig):
        self.llm = AzureChatOpenAI(
            deployment_name=config.deployment,
            temperature=0.1  # Low temperature for consistency
        )
        self.doc_loader = DocumentationLoader()
        self.scenario_parser = PydanticOutputParser(pydantic_object=TestScenario)

    async def understand_feature(self, feature_name: str) -> FeatureSpec:
        """Generate understanding of what a feature should do"""

        # Load relevant documentation
        docs = await self.doc_loader.load_for_feature(feature_name)

        # Build prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a QA engineer understanding software features."),
            ("human", """
            Analyze the feature '{feature_name}' based on this documentation:
            {documentation}

            Provide:
            1. Purpose of the feature
            2. Expected inputs and their constraints
            3. Expected outputs and side effects
            4. Success criteria
            5. Common failure modes
            6. Edge cases to test

            Format as JSON.
            """)
        ])

        # Get LLM response
        response = await self.llm.ainvoke(
            prompt.format(
                feature_name=feature_name,
                documentation=docs
            )
        )

        return FeatureSpec.parse_raw(response.content)

    async def generate_test_scenarios(self, feature_spec: FeatureSpec) -> List[TestScenario]:
        """Generate concrete test scenarios from feature understanding"""

        scenarios = []

        # Generate happy path
        scenarios.append(await self._generate_happy_path(feature_spec))

        # Generate edge cases
        for edge_case in feature_spec.edge_cases:
            scenarios.append(await self._generate_edge_case_scenario(edge_case))

        # Generate error scenarios
        for failure_mode in feature_spec.failure_modes:
            scenarios.append(await self._generate_error_scenario(failure_mode))

        return scenarios
```

### 2.5 Issue Reporter Design

```python
# agentic_testing/agents/issue_reporter.py

from github import Github
from github.GithubException import GithubException
import hashlib

class IssueReporter:
    def __init__(self, config: GitHubConfig):
        # Assumes gh CLI is authenticated
        self.gh = Github(auth=self._get_gh_token())
        self.repo = self.gh.get_repo(config.repository)
        self.issue_cache = IssueCache()

    def _get_gh_token(self):
        """Get token from gh CLI config"""
        import subprocess
        result = subprocess.run(
            ['gh', 'auth', 'token'],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    async def create_issue(self, test_failure: TestFailure) -> Optional[Issue]:
        """Create a GitHub issue for a test failure"""

        # Check for duplicates
        if await self._is_duplicate(test_failure):
            return None

        # Format issue
        title = self._generate_title(test_failure)
        body = self._format_body(test_failure)
        labels = self._determine_labels(test_failure)

        # Create issue
        try:
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels
            )

            # Attach artifacts
            if test_failure.screenshot:
                await self._attach_screenshot(issue, test_failure.screenshot)

            # Cache to prevent duplicates
            self.issue_cache.add(test_failure)

            return issue

        except GithubException as e:
            logger.error(f"Failed to create issue: {e}")
            return None

    async def _is_duplicate(self, test_failure: TestFailure) -> bool:
        """Check if this issue already exists"""

        # Generate fingerprint
        fingerprint = self._generate_fingerprint(test_failure)

        # Check cache
        if self.issue_cache.contains(fingerprint):
            return True

        # Check GitHub
        query = f'repo:{self.repo.full_name} is:issue "{test_failure.error_message[:50]}"'
        issues = self.gh.search_issues(query)

        for issue in issues:
            if self._is_similar(issue, test_failure):
                return True

        return False

    def _generate_fingerprint(self, failure: TestFailure) -> str:
        """Generate unique fingerprint for deduplication"""
        content = f"{failure.feature}:{failure.scenario}:{failure.error_type}"
        return hashlib.sha256(content.encode()).hexdigest()
```

### 2.6 Priority Agent Design

```python
# agentic_testing/agents/priority_agent.py

class PriorityAgent:
    def __init__(self, config: PriorityConfig):
        self.impact_weights = config.impact_weights
        self.model = self._load_priority_model()

    async def prioritize_issue(self, test_failure: TestFailure) -> Priority:
        """Determine priority of an issue"""

        features = self._extract_features(test_failure)

        # Calculate priority score
        score = 0.0

        # User impact
        if self._affects_critical_path(test_failure):
            score += self.impact_weights['critical_path']

        # Security impact
        if self._has_security_implications(test_failure):
            score += self.impact_weights['security']

        # Data loss potential
        if self._can_cause_data_loss(test_failure):
            score += self.impact_weights['data_loss']

        # Frequency
        frequency = await self._estimate_frequency(test_failure)
        score += frequency * self.impact_weights['frequency']

        # Map score to priority
        if score > 0.8:
            return Priority.CRITICAL
        elif score > 0.6:
            return Priority.HIGH
        elif score > 0.4:
            return Priority.MEDIUM
        else:
            return Priority.LOW
```

## 3. Data Models

### 3.1 Core Data Structures

```python
# agentic_testing/models.py

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any

@dataclass
class TestScenario:
    """Represents a test scenario to execute"""
    id: str
    feature: str
    name: str
    description: str
    interface: Literal['cli', 'gui', 'mixed']
    steps: List[TestStep]
    expected_outcome: str
    verification: List[VerificationStep]

@dataclass
class TestStep:
    """Single step in a test scenario"""
    action: str  # 'click', 'type', 'execute', etc.
    target: str  # Element selector or command
    value: Optional[str]  # Input value if needed
    wait_for: Optional[str]  # Condition to wait for

@dataclass
class TestResult:
    """Result of executing a test"""
    scenario_id: str
    status: Literal['passed', 'failed', 'skipped', 'error']
    duration: float
    error: Optional[TestError]
    screenshots: List[str]
    logs: str

@dataclass
class TestFailure:
    """Represents a test failure that needs reporting"""
    feature: str
    scenario: str
    error_message: str
    error_type: str
    stack_trace: str
    screenshot: Optional[bytes]
    reproduction_steps: List[str]
    expected_behavior: str
    actual_behavior: str
    environment: Dict[str, str]
```

### 3.2 Configuration Models

```python
# agentic_testing/config.py

@dataclass
class TestConfig:
    """Main configuration for testing system"""
    cli_config: CLIConfig
    ui_config: UIConfig
    llm_config: LLMConfig
    github_config: GitHubConfig
    priority_config: PriorityConfig
    execution_config: ExecutionConfig

@dataclass
class CLIConfig:
    """CLI testing configuration"""
    base_command: List[str] = field(default_factory=lambda: ['uv', 'run', 'atg'])
    timeout: int = 300  # seconds
    env_vars: Dict[str, str] = field(default_factory=dict)

@dataclass
class UIConfig:
    """UI testing configuration"""
    app_path: str = 'spa/main/index.js'
    screenshot_dir: str = 'outputs/screenshots'
    viewport: Dict[str, int] = field(default_factory=lambda: {'width': 1920, 'height': 1080})
    headless: bool = False  # Run with UI for debugging

@dataclass
class LLMConfig:
    """LLM configuration"""
    deployment: str
    api_version: str = '2024-02-01'
    temperature: float = 0.1
    max_tokens: int = 4000
```

## 4. Implementation Patterns

### 4.1 Page Object Model for UI Testing

```typescript
// agentic_testing/pages/build_tab.ts

export class BuildTabPage {
    constructor(private page: Page) {}

    async navigateTo(): Promise<void> {
        await this.page.click('[data-testid="build-tab"]');
        await this.page.waitForSelector('[data-testid="build-content"]');
    }

    async enterTenantId(tenantId: string): Promise<void> {
        await this.page.fill('[data-testid="tenant-id-input"]', tenantId);
    }

    async startScan(): Promise<void> {
        await this.page.click('[data-testid="start-scan-button"]');
    }

    async waitForCompletion(): Promise<void> {
        await this.page.waitForSelector('[data-testid="scan-complete"]', {
            timeout: 600000  // 10 minutes
        });
    }

    async getResults(): Promise<ScanResults> {
        const nodeCount = await this.page.textContent('[data-testid="node-count"]');
        const edgeCount = await this.page.textContent('[data-testid="edge-count"]');

        return {
            nodes: parseInt(nodeCount || '0'),
            edges: parseInt(edgeCount || '0')
        };
    }
}
```

### 4.2 Test Retry Pattern

```python
# agentic_testing/patterns/retry.py

class RetryHandler:
    def __init__(self, max_retries: int = 3, backoff: float = 2.0):
        self.max_retries = max_retries
        self.backoff = backoff

    async def execute_with_retry(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry"""
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = self.backoff ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)

        raise last_exception
```

### 4.3 State Management Pattern

```python
# agentic_testing/patterns/state.py

class StateManager:
    """Manages application and test state"""

    def __init__(self):
        self.checkpoints = []
        self.current_state = None

    async def checkpoint(self, name: str):
        """Save current state"""
        state = await self._capture_state()
        self.checkpoints.append({
            'name': name,
            'state': state,
            'timestamp': datetime.now()
        })

    async def restore(self, checkpoint_name: str):
        """Restore to a previous state"""
        checkpoint = next(
            (c for c in self.checkpoints if c['name'] == checkpoint_name),
            None
        )

        if checkpoint:
            await self._restore_state(checkpoint['state'])
```

## 5. Deployment Architecture

### 5.1 Directory Structure

```
azure-tenant-grapher/
├── agentic_testing/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── config.py
│   ├── models.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── cli_agent.py
│   │   ├── electron_ui_agent.ts
│   │   ├── comprehension_agent.py
│   │   ├── issue_reporter.py
│   │   └── priority_agent.py
│   ├── patterns/
│   │   ├── retry.py
│   │   ├── state.py
│   │   └── deduplication.py
│   ├── pages/           # Page Object Model
│   │   ├── build_tab.ts
│   │   ├── generate_iac_tab.ts
│   │   └── status_tab.ts
│   ├── scenarios/       # Test scenarios
│   │   ├── happy_path.yaml
│   │   ├── edge_cases.yaml
│   │   └── error_cases.yaml
│   └── utils/
│       ├── screenshot.py
│       ├── logging.py
│       └── metrics.py
```

### 5.2 CI/CD Integration

```yaml
# .github/workflows/agentic-testing.yml

name: Agentic Testing

on:
  schedule:
    - cron: '0 */4 * * *'  # Every 4 hours
  workflow_dispatch:
    inputs:
      test_suite:
        description: 'Test suite to run'
        required: false
        default: 'smoke'
        type: choice
        options:
          - smoke
          - full
          - regression

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Install dependencies
        run: |
          pip install -r agentic_testing/requirements.txt
          npm install -g playwright
          playwright install electron

      - name: Configure environment
        env:
          AZURE_TENANT_ID: ${{ secrets.TEST_TENANT_ID }}
          AZURE_CLIENT_ID: ${{ secrets.TEST_CLIENT_ID }}
          AZURE_CLIENT_SECRET: ${{ secrets.TEST_CLIENT_SECRET }}
        run: |
          echo "Setting up test environment"
          gh auth setup-git

      - name: Run tests
        run: |
          python -m agentic_testing.orchestrator \
            --config agentic_testing/config.yaml \
            --suite ${{ github.event.inputs.test_suite || 'smoke' }}

      - name: Upload artifacts
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: |
            outputs/screenshots/
            outputs/logs/
            outputs/test-results.json
```

## 6. Error Handling and Recovery

### 6.1 Error Categories

```python
# agentic_testing/errors.py

class TestingError(Exception):
    """Base exception for testing system"""
    pass

class AgentError(TestingError):
    """Error in agent execution"""
    pass

class ApplicationError(TestingError):
    """Error in application under test"""
    pass

class InfrastructureError(TestingError):
    """Error in testing infrastructure"""
    pass
```

### 6.2 Recovery Strategies

```python
# agentic_testing/recovery.py

class RecoveryManager:
    async def recover_from_error(self, error: Exception, context: TestContext):
        """Implement recovery based on error type"""

        if isinstance(error, ApplicationCrashError):
            await self._restart_application()
        elif isinstance(error, Neo4jConnectionError):
            await self._reconnect_neo4j()
        elif isinstance(error, NetworkTimeoutError):
            await self._wait_and_retry()
        else:
            await self._reset_to_checkpoint()
```

## 7. Monitoring and Metrics

### 7.1 Metrics Collection

```python
# agentic_testing/metrics.py

class MetricsCollector:
    def __init__(self):
        self.metrics = {
            'tests_executed': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'issues_created': 0,
            'false_positives': 0,
            'execution_time': 0.0
        }

    async def record_test_result(self, result: TestResult):
        self.metrics['tests_executed'] += 1
        if result.status == 'passed':
            self.metrics['tests_passed'] += 1
        elif result.status == 'failed':
            self.metrics['tests_failed'] += 1
```

### 7.2 Logging Strategy

```python
# agentic_testing/utils/logging.py

import logging
from rich.logging import RichHandler

def setup_logging(level: str = 'INFO'):
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RichHandler(rich_tracebacks=True),
            logging.FileHandler('outputs/logs/agentic_testing.log')
        ]
    )
```

## 8. Security Considerations

### 8.1 Credential Management

```python
# agentic_testing/security.py

class CredentialManager:
    def __init__(self):
        self.vault = self._init_vault()

    def get_azure_credentials(self):
        """Get Azure credentials from environment"""
        return {
            'tenant_id': os.environ['AZURE_TENANT_ID'],
            'client_id': os.environ['AZURE_CLIENT_ID'],
            'client_secret': os.environ['AZURE_CLIENT_SECRET']
        }

    def sanitize_for_logging(self, text: str) -> str:
        """Remove sensitive data from logs"""
        patterns = [
            (r'Bearer [A-Za-z0-9\-._~+/]+', 'Bearer ***'),
            (r'password["\']?\s*[:=]\s*["\']?[^"\'\\s]+', 'password=***'),
            (r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '***-***-***-***')
        ]

        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text
```

## 9. Performance Optimizations

### 9.1 Parallel Execution

```python
# agentic_testing/parallel.py

class ParallelExecutor:
    def __init__(self, max_workers: int = 4):
        self.semaphore = asyncio.Semaphore(max_workers)

    async def execute_parallel(self, tasks: List[Callable]) -> List[Any]:
        """Execute tasks in parallel with concurrency limit"""

        async def run_with_semaphore(task):
            async with self.semaphore:
                return await task()

        return await asyncio.gather(
            *[run_with_semaphore(task) for task in tasks]
        )
```

### 9.2 Caching Strategy

```python
# agentic_testing/cache.py

class TestCache:
    def __init__(self):
        self.cache = {}
        self.ttl = 3600  # 1 hour

    async def get_or_compute(self, key: str, compute_func: Callable):
        """Get from cache or compute if missing"""

        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.ttl:
                return entry['value']

        value = await compute_func()
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }

        return value
```

---

*This design document specifies HOW to implement the Agentic Testing System to meet all requirements defined in the Requirements Document.*
