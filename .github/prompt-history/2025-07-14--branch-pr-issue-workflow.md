### User Prompt
Branch/PR & Issue workflow

Objectives:
1. Create and switch to branch `feat/cli-neo4j-autostart`.
2. Commit all staged Neo4j-autostart refactor changes.
3. Push the branch to origin and open a draft PR.
4. Create a GitHub Issue titled “Add integration test for atg build auto-starts Neo4j” with description:
   ```
   Ensure the command `atg build --no-dashboard` starts Neo4j automatically when it isn’t running and proceeds without error. Add an integration test under tests/cli to validate this.
   ```
   Label it `ai-created`.
5. Locally validate by executing:
   ```
   docker rm -f azure-tenant-grapher-neo4j || true
   uv run azure-tenant-grapher build --no-dashboard
   ```
   Capture exit status and confirm container up (`docker ps`).

Deliverables:
• Confirmation of branch, commit SHA, PR URL.  
• Confirmation Issue URL.  
• Output summary of validation run.

Allowed tools: execute_command for git/gh/docker/uv, etc.  
After completion use attempt_completion to report results.

These instructions supersede generic code-mode rules.