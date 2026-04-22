# Optimad Python — Agent Instructions

## Domain
Python utilities and services for Optimad.

## Stack
Python, FastAPI, pytest.

## Architecture Map
- `src/`: Application source code.

## Output Style
- Short sentences. No fluff. No "I'll help you with".
- No explanations unless asked. Code only when code needed.
- Bad: "I'll now proceed to implement the authentication middleware..."
- Good: "Done. middleware.ts updated."

## Token Efficiency
- Think first. Read files before writing code.
- Prefer targeted edits over full file rewrites.
- Read each file once unless it changed.
- Run tests before marking task complete.

**CRITICAL:** Read modular instructions before starting:
- [.github/instructions/01-architecture-and-stack.md](.github/instructions/01-architecture-and-stack.md)
- [.github/instructions/02-ui-and-styling.md](.github/instructions/02-ui-and-styling.md)
- [.github/instructions/03-testing-and-linting.md](.github/instructions/03-testing-and-linting.md)
- [.github/instructions/04-ai-workflow.md](.github/instructions/04-ai-workflow.md)
