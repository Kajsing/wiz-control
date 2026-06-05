# Codex Project Notes

This directory contains project-scoped Codex configuration. It is intentionally
small: repository conventions live in `AGENTS.md`, while this directory is for
Codex settings and optional future automation.

## Current Setup

- `config.toml` keeps local Codex work in the repository workspace by default.
- Approval prompts remain enabled for commands that need more access.
- Web search uses cached mode by default to reduce live-page exposure.
- Hooks remain enabled, but this repository does not define project hooks yet.

## Where To Put Codex Changes

- Use `AGENTS.md` for durable repository instructions, commands, style rules,
  testing expectations, and review guidance.
- Use `.codex/config.toml` for project-scoped Codex settings such as sandbox,
  approval, web search, model, MCP, or feature toggles.
- Add `.codex/hooks.json` only when the repository needs a concrete lifecycle
  check. Hooks require trust review before they run.
- Prefer user-level MCP configuration for personal services. Add project MCP
  servers only when they are required for this repository and safe to share.
