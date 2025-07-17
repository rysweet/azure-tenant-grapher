### User Prompt (2025-07-16 18:08:09 PDT)
Create a new GitHub issue for the following feature using the dedicated AI-created issue template (`.github/ISSUE_TEMPLATE/ai-created-issue.md`) and label it as `ai-created`:

**Title:**  
Feature: specify domain name to use for all entities that require a domain name (eg user account) when running the generate-iac or spec commands

**Description:**  
When running the generate-iac or spec commands, users should be able to specify a domain name to be used for all entities (such as user accounts) that require a domain name. The desired outcome is that all user account creation and similar operations in the generated scripts will succeed because they will use valid domain names for the tenants specified, substituting the provided domain name for any domain name that might already be in the graph.

**Context:**  
- This feature is needed to ensure generated IaC scripts are always valid and do not fail due to invalid or missing domain names.
- The implementation should allow the domain name to be specified as a parameter to the relevant commands.
- All documentation, help, and examples must be updated to reflect this new capability.

**Reasoning:**  
Currently, domain names may be missing or invalid in the graph, causing failures in user account creation or other operations. By allowing the user to specify a domain name, we ensure all generated entities have valid, tenant-specific domain names, improving reliability and usability.

**Instructions:**  
- Use the correct issue template and label.
- Include all the above context and reasoning in the issue body.
- Only perform the work outlined in these instructions and do not deviate.
- Signal completion by using the attempt_completion tool, providing a concise yet thorough summary of the outcome in the result parameter, as this will be the source of truth for tracking.
- These specific instructions supersede any conflicting general instructions for your mode.