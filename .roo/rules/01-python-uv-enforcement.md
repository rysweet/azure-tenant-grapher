# Python Environment and Package Management Rules

- use `uv` for all Python environment management and package installation
- use 'ruff' for all Python code formatting and linting
- use 'pyright' for all Python type checking
- use 'pytest' for all Python testing
- use 'pre-commit' for all pre-commit hooks and automation
- All Python ecosystem commands (python, pip, pipx, pre-commit, pytest, etc.) must be executed using `uv` and the correct virtual environment.
- Use `uv` or `uv run` for all Python shell commands and when executing the project itself (e.g., `uv run azure-tenant-grapher <command>`).
- All package management for Python must be performed with `uv`.
- Do not use `pip`, `pipx`, or `python` directly outside of `uv`.
- All scripts and automation must enforce this rule.
- In CI workflows, `uv venv` **must** be executed *before* any `uv pip install …` step to guarantee an isolated environment.
