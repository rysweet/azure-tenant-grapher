# Workflow Rules for All Changes

1. Ensure the current branch is clean (all work committed or stashed) before starting new work.
2. Switch to Orchestrator mode if not already in Orchestrator mode.
3. Improvement mode **MUST** evaluate gaps in the current Roo rules.
   - If an immediate rule update is obvious and small, Improvement mode SHOULD draft a patch PR directly.
   - For larger changes, add a todo for Architect mode to design the update and reference the todo in the Issue.
4. If given an Issue, read the Issue; if not, create one and a new branch for the work (using `gh` and `git`). Always use the Issue Template for new issues.
5. Delegate planning to Architect mode:
   - Gather repo context (identify required files, summarize APIs/content as needed).
   - Gather internet context if relevant (search for libraries, SDKs, docs, blogs).
   - Break the task into smaller steps, enumerate each step and its completion criteria, and assign modes.
   - Update the Issue with the plan and context.
6. Switch back to Orchestrator mode and implement changes step by step.
7. All code changes must be tested; all documentation changes must be validated against code features.
8. Always run pre-commit and resolve any failing checks.
9. The task is not complete until all tests and pre-commit checks pass.
10. Once tests and pre-commit pass, commit and push the work to the branch.
11. After push, create or update the PR with a summary of changes (using `gh`).
12. After a push to a PR, run `scripts/check_ci_status.sh` to check CI status. Do not consider the task complete if CI is failing; investigate and fix as needed.
