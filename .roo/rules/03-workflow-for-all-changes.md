# Workflow Rules for All Changes

- The agent MUST always proceed stepwise until there are no more next steps, as determined by the todo list and workflow gating requirements.
- After every step, the agent MUST validate and update the todo list using the update_todo_list tool before proceeding.
- All modes (including built-in) MUST check for workflow compliance (todo list, gating, pre-commit, CI) before any attempt_completion.
- Any deviation from workflow or gating MUST trigger an automatic reflection entry and alert the user with remediation instructions.
- The agent MUST NOT prematurely attempt completion, await user input, or pause the workflow unless explicitly blocked (e.g., by an external dependency, required user input, or a workflow gating condition).
- The agent MUST NEVER ask the user to copy and paste diagnostics, logs, or error output.
- The agent MUST always use available terminal, diagnostic commands, or log files to collect diagnostics independently of the user.

1. Ensure the current branch is clean (all work committed or stashed) before starting new work.
2. Switch to Orchestrator mode if not already in Orchestrator mode.
3. Improvement mode **MUST** evaluate gaps in the current Roo rules.
   - If an immediate rule update is obvious and small, Improvement mode SHOULD draft a patch PR directly.
   - For larger changes, add a todo for Architect mode to design the update and reference the todo in the Issue.
4. Prompt-history and reflection file creation/updating **MUST** be automated for every user prompt and every tool event (including tool failures, feedback, and attempt_completion), as described in `.roo/rules/02-prompt-history-and-reflection.md`.
   - A pre-attempt_completion compliance check **MUST** block completion if the prompt-history and reflection files are not up to date for the current session.
   - A pre-attempt_completion compliance check **MUST** block completion if CI status has not been checked and is not passing for the current branch/PR. The agent must run `scripts/check_ci_status.sh` or an equivalent automated check before any attempt_completion.
5. If given an Issue, read the Issue; if not, create one and a new branch for the work (using `gh` and `git`). Always use the Issue Template for new issues.
6. Delegate planning to Architect mode:
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

13. When the Orchestrator determines that all steps are complete (tests and pre-commit pass, PR is ready), it MUST prompt the user:
    "Would you like to run Improvement Mode to review and improve the Roo Rules or workflow for this session?"
    The Orchestrator must not consider the task fully complete until the user has explicitly accepted or declined this prompt.

14. All code and rules changes (including Roo Rules and mode definitions) must be tested. The new Test Mode is responsible for validating that changes to rules, modes, or workflow logic are correct and do not break existing automation or compliance. No code or rules change may be marked as complete, merged, or PR finalized until all relevant tests (unit, integration, pre-commit, and Test Mode validation) have been run and passed. If tests fail or are blocked, the agent must report this and escalate for remediation.
