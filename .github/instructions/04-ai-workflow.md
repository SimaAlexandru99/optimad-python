## Agent Coordination Rules

- Before starting, check `.progress.md` for current state.
- When working as a teammate, always check TaskList before new work.
- Never modify the same file as another concurrent agent.
- After 2 tool failures: STOP, change approach, explain what failed.

## Circuit Breaker Rules (The 3-5-2 Protocol)

These rules are MANDATORY to prevent loops and resource exhaustion.

### Level 1 — Per File (Micro)
- **3 failed edits** on the same file → **STOP**.
- Re-read the original request and the full file.
- Explain the conflict before attempting a 4th edit.

### Level 2 — Per Session (Meso)
- **5 total tool/command failures** in a single session → **HALT**.
- Create/Update .progress.md in the project root documenting the failure chain.
- Ask the user for a new strategy. DO NOT retry the same logic.

### Level 3 — Stack Level (Macro)
- **2 blocked sessions** across projects → **GLOBAL ALERT**.
- If multiple agents are stuck in error-loops, do not spawn new sub-agents.
- Escalate to the user with a summary of the multi-session deadlock.

## Session Management
- Use `/clear` between unrelated tasks to avoid paying for stale context.
- Use `/compact` when task 2 depends on task 1 context (compresses instead of deleting).

## Implementation Guardrails
- Before any edit, verify the current state.
- After a Level 2 halt, the next action MUST be a Research task, not an Act task.
