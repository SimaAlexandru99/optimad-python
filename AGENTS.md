# Optimad Python — Agent Entry Point

See [CLAUDE.md](CLAUDE.md) for canonical agent instructions.

## Token Optimization
- **RTK**: Prefix shell commands with `rtk` for 60-90% compressed output.
  - `rtk git status`, `rtk git diff`, `rtk npm test`, etc.
  - On failure: full output saved to tee log — read it, don't re-run.
- **code-review-graph**: Use graph tools before Grep/Glob/Read to explore codebase.
  - Faster, fewer tokens, structural context (callers, dependents, test coverage).
  - Build once: `code-review-graph build`

This file exists for agents that prefer AGENTS.md over CLAUDE.md.
