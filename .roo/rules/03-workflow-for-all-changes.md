# Workflow Rules for All Changes

1. Ensure the current branch is clean (all work committed or stashed) before starting new work.
2. Switch to Orchestrator mode if not already in Orchestrator mode.
3. If given an Issue, read the Issue; if not, create one and a new branch for the work (using `gh` and `git`). Always use the Issue Template for new issues.
4. Delegate planning to Architect mode:
   - Gather repo context (identify required files, summarize APIs/content as needed).
   - Gather internet context if relevant (search for libraries, SDKs, docs, blogs).
   - Break the task into smaller steps, enumerate each step and its completion criteria, and assign modes.
   - Update the Issue with the plan and context.
5. Switch back to Orchestrator mode and implement changes step by step.
6. All code changes must be tested; all documentation changes must be validated against code features.
7. Always run pre-commit and resolve any failing checks.
8. The task is not complete until all tests and pre-commit checks pass.
9. Once tests and pre-commit pass, commit and push the work to the branch.
10. After push, create or update the PR with a summary of changes (using `gh`).
11. After a push to a PR, run `scripts/check_ci_status.sh` to check CI status. Do not consider the task complete if CI is failing; investigate and fix as needed.
