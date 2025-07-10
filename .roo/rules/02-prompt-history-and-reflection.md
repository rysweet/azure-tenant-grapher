# Prompt History and Reflection Rules

**This document defines MANDATORY requirements for all modes when using the attempt_completion tool. These requirements ensure proper feedback tracking, natural language communication, and task completion signaling. Each mode is responsible for directly creating and updating the prompt-history and reflection files.**

## Universal Attempt Completion Requirements

- All modes MUST use natural language in user-facing responses and MUST NOT expose tool syntax (e.g., XML tags) to users.
- Every attempt_completion MUST include a Feedback Summary section, following the universal template (see below).
- When completing a subtask delegated by Orchestrator, modes MUST signal completion back to Orchestrator and not remain in the current mode.
- Feedback data MUST be written to `.github/prompt-history/reflection--{session-name}.md` (for markdown feedback reports) per below.
- Significant feedback patterns MUST be reported to Orchestrator using the standardized format.
- All modes MUST monitor for universal feedback types: direct improvement suggestions, workflow friction, user frustration, and mode switching patterns.
- Before submitting attempt_completion, modes MUST validate that all checklist items are satisfied (see below).

## Enforcement and Implementation

**MANDATORY FILE CREATION REQUIREMENTS:**

- **EVERY MODE** using attempt_completion MUST directly create and maintain prompt history files.
- **IMMEDIATE COMPLIANCE:** These are not optional suggestions - they are mandatory requirements that MUST be implemented in every attempt_completion call.
- **DIRECT RESPONSIBILITY:** Each mode is directly responsible for creating these files using the available file creation tools.

**Detailed Requirements:**

- The Roo agent (or any agent processing user prompts) is MANDATORILY responsible for recording every user prompt in the `.github/prompt-history/` directory.
- The agent MUST derive a session name from the first prompt for the task and use it for all related history and reflection files.
- Each prompt received from the user MUST be appended to `.github/prompt-history/{session-name}.md` by the agent immediately after processing.
- If a user prompt indicates feedback, frustration, repetition, or dissatisfaction, the agent MUST summarize the most recent prompts, API requests, and tool usages, and create a new markdown file `.github/prompt-history/reflection--{session-name}.md` with this summary.
- A script or automation (e.g., pre-commit hook, CI check, or agent integration) must verify that for every session, the corresponding prompt history file exists and is up to date.
- The repository must include a pre-commit/CI enforcement script (e.g., `scripts/check_prompt_history.py`) that:
  - Checks for at least one session file in `.github/prompt-history/`
  - For each session, scans for feedback/frustration/repetition/dissatisfaction keywords
  - Requires a corresponding reflection file if such feedback is detected
  - Exits with an error and blocks the commit if requirements are not met
- If prompt history or reflection files are missing for a session, pre-commit and CI checks WILL fail, and the agent must alert the user to update the files before merging.
- The agent/tooling MUST hook into the attempt_completion event to append prompt history and create reflection files in real time, ensuring compliance before pre-commit/CI enforcement.

**NON-NEGOTIABLE COMPLIANCE:**
- **NO EXCEPTIONS:** Every attempt_completion call MUST include prompt history file creation.
- **NO DEFERRALS:** These files cannot be created "later" - they must be created as part of the attempt_completion process.
- **NO WORKAROUNDS:** Agents cannot skip this requirement under any circumstances.

## Feedback Summary Template

```markdown
## Task Summary
[Brief description of what was accomplished]

## Implementation Details
[Key changes made, files created/modified, etc.]

## Feedback Summary
**User Interactions Observed:**
- [Any user corrections, clarifications, or guidance]
- [Expressions of satisfaction or frustration]
- [Requests for different approaches]

**Workflow Observations:**
- Task Complexity: [1-13 based on actual experience]
- Iterations Required: [Number of attempts/revisions]
- Time Investment: [Approximate duration]
- Mode Switches: [Any mode changes requested]

**Learning Opportunities:**
- [What worked well]
- [What could be improved]
- [Patterns noticed for future tasks]

**Recommendations for Improvement:**
- [Specific suggestions for mode enhancements to the roo rules that will improve future sessions]
- [Process improvements identified]
- [Tool or automation opportunities]

## Next Steps
[Any follow-up actions or recommendations]
```

## Rationale

- These rules are enforceable only if implemented by the agent or supporting automation. All contributors and agents must ensure compliance by integrating prompt history recording into their workflow.
- Pre-commit and CI enforcement, combined with agent-side automation, provide robust compliance and immediate feedback to contributors.
- Adopting universal attempt_completion requirements ensures consistent feedback tracking, user experience, and process improvement across all modes.
