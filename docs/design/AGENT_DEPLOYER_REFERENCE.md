# Agent Deployer Reference

Technical reference for the autonomous deployment agent implementation.

## Module Overview

**Location:** `src/deployment/agent_deployer.py`

**Size:** ~150-200 lines of code

**Philosophy:** Ruthlessly simple, single-module implementation using Claude SDK AutoMode for AI-driven error recovery.

**Key Design Decisions:**
- Generic AI-driven fix approach (no pre-defined error strategies)
- Simple state tracking using loop variables
- Delegates to existing deployment backends (Terraform, Bicep, ARM)
- Stateless between iterations (all state in files and loop vars)

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     AgentDeployer                            │
│  - deploy() : DeploymentResult                              │
│  - _execute_iteration() : IterationResult                   │
│  - _analyze_and_fix() : FixResult                          │
│  - _generate_report() : str                                 │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ uses
                  ↓
┌─────────────────────────────────────────────────────────────┐
│           Existing Deployment Backends                       │
│  - TerraformDeployer                                        │
│  - BicepDeployer                                            │
│  - ARMDeployer                                              │
└─────────────────────────────────────────────────────────────┘
                  ↑
                  │ delegates to
                  │
┌─────────────────┴───────────────────────────────────────────┐
│              Claude SDK AutoMode                             │
│  - analyze_error(error_output) : Analysis                   │
│  - generate_fix(analysis) : FixInstructions                 │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Command (atg deploy --agent)
       ↓
AgentDeployer.deploy()
       ↓
Loop (max_iterations):
  ├─→ _execute_iteration()
  │      ├─→ Select Backend (Terraform/Bicep/ARM)
  │      ├─→ Execute Deployment
  │      ├─→ Capture stdout/stderr
  │      └─→ Return IterationResult
  │
  ├─→ Check Success
  │      ├─→ YES: Break loop, generate report
  │      └─→ NO: Continue to fix
  │
  └─→ _analyze_and_fix()
         ├─→ Claude SDK AutoMode
         │      ├─→ Analyze error output
         │      └─→ Generate fix instructions
         ├─→ Apply fix to IaC files
         └─→ Return FixResult

Final: _generate_report()
       ↓
Return DeploymentResult
```

## Classes and Methods

### AgentDeployer

Main class implementing autonomous deployment loop.

```python
class AgentDeployer:
    """Autonomous deployment agent with AI-powered error recovery.

    Attributes:
        iac_path: Path to IaC files
        format: IaC format (terraform, bicep, arm)
        max_iterations: Maximum deployment attempts
        timeout: Timeout per operation (seconds)
        backend: Deployment backend instance
    """

    def __init__(
        self,
        iac_path: Path,
        format: str,
        max_iterations: int = 5,
        timeout: int = 300,
    ):
        """Initialize agent deployer.

        Args:
            iac_path: Path to generated IaC files
            format: IaC format (auto-detected if not specified)
            max_iterations: Maximum number of deployment attempts
            timeout: Timeout for each deployment operation
        """
```

**Initialization Logic:**
1. Validate IaC path exists
2. Auto-detect format if not specified
3. Select appropriate backend (Terraform/Bicep/ARM)
4. Initialize Claude SDK client
5. Set up iteration tracking

### deploy()

Main entry point for autonomous deployment.

```python
def deploy(self) -> DeploymentResult:
    """Execute autonomous deployment with error recovery.

    Returns:
        DeploymentResult containing:
        - success: bool
        - iterations: List[IterationResult]
        - report: str (markdown report)
        - final_error: Optional[str]

    Raises:
        DeploymentError: If critical error occurs
    """
```

**Algorithm:**
```
1. Initialize iteration counter = 0
2. While iteration < max_iterations:
   a. iteration += 1
   b. result = _execute_iteration(iteration)
   c. If result.success:
      - Break loop
      - Generate success report
   d. Else:
      - fix = _analyze_and_fix(result.error)
      - Apply fix to IaC files
      - Continue loop
3. Generate final report (success or failure)
4. Return DeploymentResult
```

**Error Handling:**
- Catches all exceptions during iteration
- Preserves error context for AI analysis
- Never loses iteration history
- Graceful degradation on AI failure (logs error, returns failure)

### _execute_iteration()

Execute single deployment attempt.

```python
def _execute_iteration(self, iteration: int) -> IterationResult:
    """Execute one deployment iteration.

    Args:
        iteration: Iteration number (1-indexed)

    Returns:
        IterationResult containing:
        - iteration_num: int
        - success: bool
        - duration: float (seconds)
        - stdout: str
        - stderr: str
        - error: Optional[str]
    """
```

**Implementation Details:**
1. Create iteration-specific working directory
2. Copy current IaC files to iteration directory
3. Execute deployment using backend:
   ```python
   result = self.backend.deploy(
       iac_path=iteration_dir,
       timeout=self.timeout,
       capture_output=True,
   )
   ```
4. Capture all output (stdout, stderr)
5. Determine success/failure from exit code
6. Package results in IterationResult
7. Preserve iteration artifacts (state files, logs)

**Timeout Handling:**
- Uses subprocess timeout mechanism
- Captures partial output on timeout
- Treats timeout as failure (allows AI to analyze)

### _analyze_and_fix()

Analyze error and generate fix using AI.

```python
def _analyze_and_fix(self, error_context: str) -> FixResult:
    """Analyze deployment error and generate fix.

    Args:
        error_context: Error output from failed deployment

    Returns:
        FixResult containing:
        - analysis: str (AI's error analysis)
        - fix_instructions: str (AI's fix instructions)
        - files_modified: List[Path]
        - success: bool
    """
```

**AI Interaction:**
```python
prompt = f"""
Analyze this deployment error and provide fix:

Error Output:
{error_context}

IaC Format: {self.format}
Iteration: {self.current_iteration}

Provide:
1. Root cause analysis
2. Specific fix instructions
3. File modifications needed
"""

response = await claude_sdk_client.query(prompt)
```

**Fix Application:**
1. Parse AI response for fix instructions
2. Identify files to modify
3. Apply modifications (edit IaC templates)
4. Validate modifications (basic syntax check)
5. Return FixResult with modification details

**Error Recovery:**
- If AI fails to provide fix: log error, return failure
- If fix application fails: rollback changes, return failure
- If fix is invalid: skip application, return failure

### _generate_report()

Generate comprehensive deployment report.

```python
def _generate_report(
    self,
    iterations: List[IterationResult],
    final_status: str,
) -> str:
    """Generate markdown deployment report.

    Args:
        iterations: List of all iteration results
        final_status: SUCCESS or FAILURE

    Returns:
        Markdown-formatted report string
    """
```

**Report Structure:**
```markdown
# Deployment Report

## Summary
- Status: {final_status}
- Total Iterations: {count}
- Total Duration: {duration}
- Resources Deployed: {count}

## Iteration History
[For each iteration]
### Iteration {N} ({status})
- Duration: {seconds}
- Error: {error_message}
- AI Analysis: {analysis}
- Fix Applied: {fix_description}
- Files Modified: {file_list}

## Recommendations
[AI-generated recommendations for future deployments]

## Troubleshooting
[Relevant troubleshooting steps based on errors encountered]
```

**Report Generation Logic:**
1. Calculate summary statistics
2. Format iteration history chronologically
3. Extract AI analyses and fixes
4. Generate recommendations based on patterns
5. Add troubleshooting section for failures
6. Write to `deployment_report.md` in IaC directory

## Data Structures

### DeploymentResult

```python
@dataclass
class DeploymentResult:
    """Result of autonomous deployment."""
    success: bool
    iterations: List[IterationResult]
    total_duration: float
    resources_deployed: int
    report: str
    final_error: Optional[str] = None
```

### IterationResult

```python
@dataclass
class IterationResult:
    """Result of single deployment iteration."""
    iteration_num: int
    success: bool
    duration: float
    stdout: str
    stderr: str
    exit_code: int
    error: Optional[str] = None
    timestamp: str
```

### FixResult

```python
@dataclass
class FixResult:
    """Result of AI-generated fix."""
    analysis: str
    fix_instructions: str
    files_modified: List[Path]
    success: bool
    error: Optional[str] = None
```

## Integration Points

### CLI Integration

```python
# src/cli_commands.py

def deploy_command(
    iac_path: Path,
    agent: bool = False,
    max_iterations: int = 5,
    timeout: int = 300,
    **kwargs
):
    """Deploy IaC with optional agent mode."""
    if agent:
        deployer = AgentDeployer(
            iac_path=iac_path,
            max_iterations=max_iterations,
            timeout=timeout,
        )
        result = deployer.deploy()

        if result.success:
            click.echo(f"✓ Deployment succeeded in {result.total_duration}s")
        else:
            click.echo(f"✗ Deployment failed after {len(result.iterations)} iterations")

        click.echo(f"Report: {iac_path / 'deployment_report.md'}")

        sys.exit(0 if result.success else 1)
    else:
        # Standard deployment (no agent)
        ...
```

### Backend Interface

All deployment backends must implement:

```python
class DeploymentBackend(ABC):
    """Abstract base for deployment backends."""

    @abstractmethod
    def deploy(
        self,
        iac_path: Path,
        timeout: int,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """Execute deployment.

        Args:
            iac_path: Path to IaC files
            timeout: Operation timeout
            capture_output: Capture stdout/stderr

        Returns:
            CompletedProcess with returncode, stdout, stderr
        """
```

**Existing implementations:**
- `TerraformDeployer`: Runs `terraform apply -auto-approve`
- `BicepDeployer`: Runs `az deployment group create`
- `ARMDeployer`: Runs `az deployment group create`

## Configuration

### Command-Line Arguments

```python
@click.command()
@click.option("--agent", is_flag=True, help="Enable autonomous deployment")
@click.option("--max-iterations", default=20, help="Maximum iterations")
@click.option("--timeout", default=6000, help="Timeout per operation")
@click.option("--format", type=click.Choice(["terraform", "bicep", "arm"]))
def deploy(**kwargs):
    ...
```

### Environment Variables

```python
# Optional environment overrides
MAX_ITERATIONS = os.getenv("ATG_DEPLOY_MAX_ITERATIONS", 5)
TIMEOUT = os.getenv("ATG_DEPLOY_TIMEOUT", 300)
AGENT_DEBUG = os.getenv("ATG_AGENT_DEBUG", "false").lower() == "true"
```

### Config File Support

```yaml
# .atg/deploy_config.yaml (optional)
agent:
  max_iterations: 10
  timeout: 600
  preserve_iterations: true

logging:
  agent_decisions: true
  verbose: false
```

## Testing Strategy

### Unit Tests

```python
# tests/test_agent_deployer.py

def test_agent_deployer_init():
    """Test AgentDeployer initialization."""

def test_execute_iteration_success():
    """Test successful deployment iteration."""

def test_execute_iteration_failure():
    """Test failed deployment iteration."""

def test_analyze_and_fix():
    """Test AI error analysis and fix generation."""

def test_deploy_success_first_iteration():
    """Test deployment succeeds on first try."""

def test_deploy_success_after_retries():
    """Test deployment succeeds after fixing errors."""

def test_deploy_max_iterations_reached():
    """Test deployment fails after max iterations."""

def test_generate_report():
    """Test report generation."""
```

### Integration Tests

```python
# tests/integration/test_agent_deploy_e2e.py

def test_terraform_agent_deploy():
    """End-to-end test with Terraform backend."""

def test_bicep_agent_deploy():
    """End-to-end test with Bicep backend."""

def test_agent_fixes_provider_error():
    """Test agent fixes missing provider error."""

def test_agent_fixes_sku_error():
    """Test agent fixes invalid SKU error."""
```

### Test Mocking Strategy

Mock Claude SDK for deterministic tests:

```python
@patch("claude_sdk.ClaudeSDKClient")
def test_ai_fix_generation(mock_sdk):
    mock_sdk.query.return_value = """
    Analysis: Missing Microsoft.Network provider
    Fix: Add provider registration block
    """

    deployer = AgentDeployer(...)
    fix = deployer._analyze_and_fix("Error: provider not registered")

    assert "provider registration" in fix.fix_instructions
```

## Performance Considerations

### Time Complexity

- **Best case:** O(1) - deployment succeeds first iteration
- **Average case:** O(3-4) - typical deployments need 3-4 iterations
- **Worst case:** O(max_iterations) - agent reaches iteration limit

### Space Complexity

- Preserves artifacts for each iteration: O(n * IaC_size)
- Typical overhead: ~10MB per iteration for medium deployments

### Optimization Strategies

1. **Early success detection:** Check exit code immediately
2. **Incremental fixes:** Only modify files that need changes
3. **Parallel analysis:** Analyze multiple error patterns concurrently (future)
4. **Fix caching:** Cache common fixes for reuse (future)

## Error Handling

### Critical Errors (Fail Immediately)

- IaC path doesn't exist
- Invalid format specified
- Claude SDK unavailable
- Invalid configuration

### Recoverable Errors (Retry with AI)

- Deployment failures (exit code != 0)
- Resource creation errors
- Configuration issues
- Timeout errors

### Graceful Degradation

- AI fails to analyze error → Log error, return failure
- Fix application fails → Rollback, try alternative fix
- Backend unavailable → Fall back to manual instructions

## Logging and Debugging

### Standard Logging

```python
import logging

logger = logging.getLogger("atg.agent_deployer")

# Log levels:
# DEBUG: Detailed iteration state, AI prompts/responses
# INFO: Iteration progress, fix application
# WARNING: Recoverable errors, failed fixes
# ERROR: Critical errors, deployment failures
```

### Debug Mode

Enable verbose debugging:

```bash
export ATG_AGENT_DEBUG=1
atg deploy --agent
```

**Debug output includes:**
- Full AI prompts and responses
- Detailed iteration state
- File modification diffs
- Backend execution details

## Security Considerations

### Credential Handling

- Never logs Azure credentials or tokens
- Uses existing Azure CLI authentication
- No credentials stored in iteration artifacts

### IaC Modification Safety

- Validates fix instructions before applying
- Never modifies files outside IaC directory
- Creates backups before modifications
- Rollback on validation failure

### AI Prompt Safety

- Sanitizes error output before sending to AI
- Removes sensitive data (subscription IDs, resource names, etc.)
- Uses structured prompts to prevent injection

## Future Enhancements

### Planned Features

1. **Custom fix strategies:** User-defined fix patterns
2. **Parallel deployments:** Deploy resource groups concurrently
3. **Fix caching:** Reuse successful fixes for similar errors
4. **Learning from history:** Improve fixes based on success rate
5. **Integration with state management:** Handle Terraform state corruption
6. **Multi-backend coordination:** Deploy with multiple IaC formats simultaneously

### Extension Points

```python
class FixStrategy(ABC):
    """Abstract base for custom fix strategies."""

    @abstractmethod
    def can_handle(self, error: str) -> bool:
        """Check if strategy can handle error."""

    @abstractmethod
    def generate_fix(self, error: str) -> FixResult:
        """Generate fix for error."""
```

## Related Documentation

- [Autonomous Deployment Guide](../guides/AUTONOMOUS_DEPLOYMENT.md) - User-facing guide
- [IaC Generation](../SCALE_OPERATIONS.md) - Generate deployable IaC
- [Deployment Backends](../../src/deployment/) - Implementation details
- [Claude SDK Integration](https://docs.anthropic.com/claude-sdk) - AI integration

## Contributing

When extending the agent deployer:

1. Maintain ruthless simplicity (single file, ~200 lines)
2. Use generic AI approach (no hard-coded error patterns)
3. Preserve all iteration artifacts
4. Generate comprehensive reports
5. Add tests for new error scenarios
6. Update documentation for new features

**Code review checklist:**
- [ ] No pre-defined fix strategies (keep AI-driven)
- [ ] Error handling is comprehensive
- [ ] Report generation includes new scenarios
- [ ] Tests cover success and failure paths
- [ ] Documentation updated
- [ ] Performance impact acceptable
