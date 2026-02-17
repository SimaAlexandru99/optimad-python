# Agent Stack - Project Configuration

This document outlines the AI agents and skills configured for this project.

## Overview

The project uses LNAI (Agent Stack Weekly) for unified AI coding tool configuration across:
- **Claude Code** - AI-powered code generation and analysis
- **Cursor IDE** - IDE-integrated AI features
- **GitHub Copilot** - Code completion and suggestions

## Configuration Sources

All agent and skill definitions are maintained in the `.ai/` directory:
- `.ai/agents/` - Individual agent definitions and prompts
- `.ai/skills/` - Reusable skill implementations
- `.ai/settings.json` - Project-specific agent configuration
- `.ai/config.json` - Meta configuration and tool settings

## Key Agents

Refer to `.ai/agents/` directory for individual agent documentation and capabilities.

Common agent roles include:
- Code Review - Performs comprehensive code analysis
- DevOps - Infrastructure and deployment automation
- Testing - Test generation and optimization
- Database - Schema design and query optimization
- UI/UX - Component design and accessibility

## How to Update Configuration

1. **Edit Configuration**:
   ```bash
   edit .ai/settings.json
   ```

2. **Sync to All Tools**:
   ```bash
   lnai sync
   ```

3. **Validate**:
   ```bash
   lnai validate
   ```

4. **Commit Changes**:
   ```bash
   git add .ai/ .claude/ .cursor/
   git commit -m "chore: update agent configuration"
   ```

## Project Rules

Apply the guidance from this file for project files in `app/`, `components/`, `lib/`, `hooks/`, `content/`, and `scripts/`.
Use skills in `.ai/skills/` for specialized implementation patterns.

## Resources

- [LNAI Documentation](https://github.com/anomalyco/lnai)
- [Agent Stack Weekly](https://agentstack.sh)
- [Claude Code Documentation](https://Claude.ai/docs)

