# Python Environment and Package Management Rules

- All Python ecosystem commands (python, pip, pipx, pre-commit, pytest, etc.) must be executed using `uv` and the correct virtual environment.
- Use `uv` or `uv run` for all Python shell commands and when executing the project itself (e.g., `uv run azure-tenant-grapher <command>`).
- All package management for Python must be performed with `uv`.
- Do not use `pip`, `pipx`, or `python` directly outside of `uv`.
- All scripts and automation must enforce this rule.
