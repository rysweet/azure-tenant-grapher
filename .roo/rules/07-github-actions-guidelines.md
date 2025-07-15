# GitHub Actions Guidelines

1. Always create a `uv` virtual environment in any job that installs Python dependencies, before invoking `uv pip install …`.

   ```yaml
   - name: Create uv virtual environment
     run: uv venv
   ```

2. When polling workflow runs with `gh`:
   - Limit to **3** consecutive attempts per run ID.
   - If still “in progress,” either:
     - Wait with exponential backoff, **or**
     - Ask the user to confirm status or provide logs.
   - Avoid hitting GitHub API rate limits and triggering “tool repetition limit” errors.

3. Use user-supplied error snippets when CLI log retrieval fails; do **not** discard them in favour of continued polling.