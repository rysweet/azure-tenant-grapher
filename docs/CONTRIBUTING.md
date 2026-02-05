# Contributing to Azure Tenant Grapher

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/azure-tenant-grapher.git`
3. Create a feature branch: `git checkout -b feat/my-feature`
4. Make your changes
5. Test your changes
6. Submit a pull request

## Development Setup

See [Installation Guide](quickstart/installation.md) for basic setup, then:

```bash
# Install development dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Run tests
./scripts/run_tests_with_artifacts.sh
```

## Code Style

### Python

- Follow PEP 8
- Use type hints for function signatures
- Maximum line length: 88 characters (Black default)
- Run formatters before committing:

```bash
# Format code
uv run ruff format src scripts tests

# Check linting
uv run ruff check src scripts tests

# Type checking
uv run pyright
```

### Pre-commit Hooks

Pre-commit hooks will automatically:
- Format code with Ruff
- Check types with Pyright
- Run security checks with Bandit

## Testing

### Running Tests

```bash
# All tests
./scripts/run_tests_with_artifacts.sh

# Specific test file
uv run pytest tests/test_specific.py -v

# With coverage
uv run pytest --cov=src --cov-report=term-missing
```

### Writing Tests

- Place tests in `tests/` directory
- Use `pytest` for test framework
- Mock Azure SDK responses for unit tests
- Use testcontainers for integration tests
- Target 40% minimum code coverage

## Pull Request Process

1. **Update Documentation**
   - Update relevant documentation in `docs/`
   - Add docstrings to new functions
   - Update README.md if adding user-facing features

2. **Run Tests**
   - Ensure all tests pass
   - Add tests for new functionality
   - Verify coverage doesn't decrease

3. **Run Linters**
   ```bash
   uv run pre-commit run --all-files
   ```

4. **Create Pull Request**
   - Use descriptive title (e.g., "feat: Add cross-tenant deployment")
   - Reference related issues
   - Describe changes and rationale
   - Include screenshots for UI changes

5. **Address Review Feedback**
   - Respond to reviewer comments
   - Make requested changes
   - Re-request review when ready

## Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(iac): Add support for Terraform import blocks

Add --auto-import-existing flag to generate-iac command.
Generates Terraform 1.5+ import blocks for existing resources.

Closes #412
```

## Documentation

### Documentation Structure

- `docs/` - All documentation
- `docs/quickstart/` - Getting started guides
- `docs/guides/` - User guides
- `docs/architecture/` - Architecture docs
- `docs/concepts/` - Conceptual explanations

### Writing Documentation

- Use Markdown format
- Follow [Diataxis framework](https://diataxis.fr/)
- Include working code examples
- Test all commands before documenting
- Link to related documentation

### Documentation Standards

- Tutorials: Step-by-step walkthrough for beginners
- How-to guides: Goal-oriented instructions
- Reference: Technical descriptions (API, schemas)
- Explanation: Conceptual discussions (architecture, design)

## Issue Reporting

### Bug Reports

Include:
- Description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Relevant logs or error messages

### Feature Requests

Include:
- Clear description of the feature
- Use case and motivation
- Proposed solution (if any)
- Alternatives considered

## Community Guidelines

- Be respectful and inclusive
- Provide constructive feedback
- Help others in issues and discussions
- Be respectful and follow community guidelines

## Questions?

- Check existing [issues](https://github.com/rysweet/azure-tenant-grapher/issues)
- Read the [documentation](https://rysweet.github.io/azure-tenant-grapher/)
- Ask in GitHub Discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
