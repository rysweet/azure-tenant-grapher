# Prompt History and Reflection Rules

- Every user prompt must be recorded in the `.github/prompt-history/` directory.
- Each session should have a name derived from the first prompt for the task.
- Each prompt received from the user should be appended to `.github/prompt-history/{session-name}.md`.
- If a user prompt indicates feedback, frustration, repetition, or dissatisfaction, summarize the most recent prompts, API requests, and tool usages.
- Create a new markdown file `.github/prompt-history/reflection--{session-name}.md` summarizing the context/history and details of the prompt.
