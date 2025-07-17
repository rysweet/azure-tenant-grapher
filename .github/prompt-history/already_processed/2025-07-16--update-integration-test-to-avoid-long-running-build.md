### User Prompt (2025-07-16)
Update integration test to avoid long-running build.

Context:
• Branch `feat/cli-neo4j-autostart`.
• Root cause analysis shows the CLI takes >120 s because it processes the full tenant when no `--resource-limit` is specified, so the test times out.
• Fix is to scope the build to a tiny workload.

Scope – perform ONLY:

1. Edit [`tests/cli/test_build_autostart.py`](tests/cli/test_build_autostart.py):
   a. Append `--resource-limit=1` to the CLI invocation list so the build completes quickly.
   b. Optionally reduce the timeout to 60 s for faster feedback.
   c. Add a comment explaining why the flag is required.

2. Run checks:
   • `uv run pytest -q tests/cli/test_build_autostart.py`
   • If it passes, run full suite: `uv run pytest -q`.
   • `pre-commit run --all-files`.

3. Commit with message “test(cli): limit resource scope to avoid timeout” and push.

4. Report back via `attempt_completion`:
   • Test results, full-suite status, pre-commit status.
   • Commit SHA.

Constraints:
• Do not modify production code or other tests.
• Keep flag value small (1) to ensure deterministic completion.

These instructions supersede any conflicting general Code-mode rules for this subtask.

---

#### Feedback (2025-07-16)
ok it still hangs - so I feel like something is wrong with the resource processing logic.
