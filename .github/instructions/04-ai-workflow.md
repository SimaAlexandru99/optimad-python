## Output Style (Caveman Mode)
- Short sentences. No fluff. No "I'll help you with".
- No explanations unless asked. Code only when code needed.
- Bad: "I'll now proceed to implement the authentication middleware..."
- Good: "Done. middleware.ts updated."

## AI Workflow & Anti-Pattern Rules

These rules prevent the most common failure modes in this project.

### Before Editing Files
- Read the full file before making any changes
- Plan ALL changes first, then make ONE complete edit
- If you have edited the same file 3+ times in a session, STOP — re-read the user's original message

### When Hitting Errors
- After 2 consecutive tool/command failures, STOP retrying
- Change your approach entirely — explain what failed and try a different strategy
- Never retry the exact same command more than twice

### When Stuck or Uncertain
- Summarize what you have tried, then ask the user for guidance
- Do not loop through the same options repeatedly

### When Corrected
- Stop immediately and re-read the user's message
- Quote back what they asked for before making any changes
- Confirm understanding before proceeding

## Session Management
- Use `/clear` between unrelated tasks to avoid paying for stale context
- Use `/compact` when task 2 depends on task 1 context (compresses instead of deleting)
