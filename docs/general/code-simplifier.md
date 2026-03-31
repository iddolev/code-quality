# code-simplifier Agent

## Installation

The `code-simplifier` agent is installed as a Claude Code plugin:

- **Plugin:** `code-simplifier@claude-plugins-official`
- **Version:** 1.0.0
- **Scope:** user
- **Agent definition file:** `C:\Users\Iddo\.claude\plugins\cache\claude-plugins-official\code-simplifier\1.0.0\agents\code-simplifier.md`

A `simplify` skill is also available, built into the Claude Code binary (not a file on disk).

## Agent Definition

```
---
name: code-simplifier
description: Simplifies and refines code for clarity, consistency, and maintainability while preserving all functionality. Focuses on recently modified code unless instructed otherwise.
model: opus
---
```

Runs on **Opus** (most capable model).

## What It Does

After code is written or modified, it reviews and refines it for clarity and consistency without changing behavior. It acts as a lightweight automated code reviewer focused purely on style and structure.

## Rules

| Principle | Details |
|---|---|
| Never break things | Functionality is sacred — only *how* the code does it can change |
| Follow project standards | ES modules, `function` over arrow functions, explicit return types, React Props patterns |
| Improve clarity | Flatten nesting, remove redundant abstractions, better names, no nested ternaries |
| Don't over-simplify | "Fewer lines" is not the goal — readable and debuggable is |
| Scope | Only recently modified code, unless told otherwise |

## How It's Triggered

Invoked via the `Agent` tool with `subagent_type: "code-simplifier:code-simplifier"`. It runs autonomously and proactively — once dispatched, it refines without asking for permission and only reports significant changes.

## Notes

- The `simplify` skill is built into the Claude Code binary — its implementation is not accessible as a markdown file.
- Whether the `simplify` skill internally dispatches the `code-simplifier` agent is unknown.
