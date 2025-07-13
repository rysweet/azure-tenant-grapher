# Workflow Rules: TODO List Management

The `update_todo_list` tool provides an explicit, version-controlled checklist for multi-step or long-running tasks. These rules define **mandatory** usage patterns for all modes.

## Mandatory Usage

- If a task involves more than one tool invocation **or** is expected to span multiple agent messages, the agent **MUST** create a todo list using `update_todo_list` before proceeding.
- The todo list **MUST** be updated every time the status of any task item changes.
- On task completion the todo list **MUST** show every item either checked (`[x]`) or explicitly deferred/removed.

## Checklist Format

Use a single-level markdown checklist (no nesting or subtasks):

```markdown
- [ ] Task description (pending)
- [-] Task description (in progress)
- [x] Task description (completed)
```

### Status Meanings

- **[ ] pending** – work not started.  
- **[-] in progress** – currently being worked on.  
- **[x] completed** – fully finished, no unresolved issues.  

## Core Principles

1. Confirm which tasks have been completed since the last update before modifying the list.  
2. Multiple statuses may be updated in a single call.  
3. Add new tasks immediately when discovered.  
4. Only mark a task **completed** when all its subtasks and dependencies are resolved.  
5. If a task is blocked, keep it *in progress* and add a new todo describing the blocking issue.  

## When to Use

- The task requires ongoing tracking across several agent messages.  
- The user provides multiple discrete instructions.  
- New actionable items are discovered during execution.  

## When NOT to Use

- The task is trivial and can be completed in a single message.  
- The user explicitly instructs not to create a todo list.  

## Task Management Guidelines

- Mark the current task as **completed** immediately after finishing its work.  
- Start the next task by marking it **in progress**.  
- Retain all unfinished tasks; update their status as needed.  
- Remove tasks only if they are no longer relevant **or** the user requests deletion.