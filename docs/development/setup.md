# Development Setup

Complete development environment setup for contributing to Azure Tenant Grapher.

## Prerequisites

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Docker & Docker Compose
- Azure CLI
- Git

## Initial Setup

### 1. Fork and Clone

```bash
# Fork on GitHub first, then clone your fork
git clone https://github.com/YOUR_USERNAME/pr600.git
cd pr600

# Add upstream remote
git remote add upstream https://github.com/rysweet/pr600.git
```

### 2. Install Dependencies

```bash
# Sync all dependencies (including dev dependencies)
uv sync

# Activate virtual environment
source .venv/bin/activate
```

### 3. Configure Environment

```bash
# Copy example environment
cp .env.example .env

# Edit .env with your values
# Required variables:
# - AZURE_TENANT_ID
# - AZURE_CLIENT_ID
# - AZURE_CLIENT_SECRET
# - NEO4J_PASSWORD
# - NEO4J_PORT
```

### 4. Install Pre-commit Hooks

```bash
uv run pre-commit install
```

This installs hooks that will:
- Format code with Ruff
- Check types with Pyright
- Run security checks with Bandit

## Development Workflow

### Create Feature Branch

```bash
# Update from upstream
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feat/my-feature
```

### Make Changes

1. Edit code
2. Add tests
3. Update documentation
4. Test locally

### Test Your Changes

```bash
# Run all tests
./scripts/run_tests_with_artifacts.sh

# Run specific test
uv run pytest tests/test_my_feature.py -v

# Run with coverage
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Lint and Format

```bash
# Format code
uv run ruff format src scripts tests

# Check linting
uv run ruff check src scripts tests

# Fix auto-fixable issues
uv run ruff check --fix src scripts tests

# Type checking
uv run pyright

# Security checks
uv run bandit -r src scripts
```

### Commit Changes

```bash
# Stage changes
git add .

# Commit (pre-commit hooks will run automatically)
git commit -m "feat: Add my feature"

# If hooks fail, fix issues and try again
```

### Push and Create PR

```bash
# Push to your fork
git push origin feat/my-feature

# Create PR on GitHub
```

## Testing

### Test Structure

```
tests/
├── unit/           # Fast unit tests
├── integration/    # Integration tests
├── e2e/           # End-to-end tests
└── fixtures/      # Test data
```

### Running Tests

```bash
# All tests
./scripts/run_tests_with_artifacts.sh

# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests
uv run pytest tests/integration/ -v

# Specific test
uv run pytest tests/unit/test_dual_graph.py::test_abstracted_id -v

# With markers
uv run pytest -m "not slow"
```

### Writing Tests

Example test:

```python
import pytest
from src.services.id_abstraction import IDAbstractionService

def test_generate_abstracted_id():
    """Test ID abstraction generates deterministic IDs"""
    service = IDAbstractionService(tenant_seed="test-seed")

    resource = {
        "id": "/subscriptions/.../virtualMachines/vm-test",
        "type": "Microsoft.Compute/virtualMachines"
    }

    # Generate ID twice - should be identical
    id1 = service.generate_id(resource)
    id2 = service.generate_id(resource)

    assert id1 == id2
    assert id1.startswith("vm-")
    assert len(id1) == 11  # vm-XXXXXXXX
```

## Debugging

### Enable Debug Mode

```bash
# Debug CLI commands
atg scan --tenant-id <tenant> --debug

# Debug tests
uv run pytest tests/ -v --log-cli-level=DEBUG
```

### Neo4j Browser

```bash
# Access Neo4j Browser
open http://localhost:7474

# Query examples
MATCH (n) RETURN n LIMIT 25;
MATCH (n:VirtualMachine) RETURN n;
```

### Docker Logs

```bash
# Neo4j logs
docker logs neo4j

# Follow logs
docker logs -f neo4j
```

## Common Tasks

### Add New Dependency

```bash
# Add to pyproject.toml under [project.dependencies]
# Then sync
uv sync

# Or use uv directly
uv add package-name
```

### Update Dependencies

```bash
# Update all
uv sync --upgrade

# Update specific package
uv add package-name --upgrade
```

### Clean Environment

```bash
# Remove virtual environment
rm -rf .venv

# Recreate
uv sync
```

### Database Operations

```bash
# Backup Neo4j
atg backup-db --output-file backup.dump

# Clear Neo4j
docker exec neo4j cypher-shell "MATCH (n) DETACH DELETE n"

# Restart Neo4j
docker restart neo4j
```

## Documentation

### Build Documentation

```bash
# Install docs dependencies
pip install -r requirements-docs.txt

# Build locally
uv run mkdocs build

# Serve locally
uv run mkdocs serve
open http://localhost:8000
```

### Add New Documentation

1. Create markdown file in `docs/`
2. Add to `mkdocs.yml` nav
3. Test locally with `mkdocs serve`
4. Commit and push

## Troubleshooting

### Pre-commit Hooks Fail

```bash
# Run hooks manually
uv run pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

### Tests Fail

```bash
# Check test dependencies
uv sync

# Check Neo4j is running
docker ps | grep neo4j

# Check environment variables
cat .env
```

### Import Errors

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall package in development mode
uv sync
```

## Additional Resources

- [Contributing Guidelines](../CONTRIBUTING.md)
- [Architecture Overview](../architecture/dual-graph.md)
- [Testing Strategy](../CONTRIBUTING.md#testing)
- [Code Style Guide](../CONTRIBUTING.md)

## Getting Help

- Check [GitHub Issues](https://github.com/rysweet/pr600/issues)
- Read [Documentation](https://rysweet.github.io/pr600/)
- Ask in GitHub Discussions
