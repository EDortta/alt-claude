# Software overview

alt-claude is a Bash launcher for Claude Code with Python helpers for project policy, session recovery, provider usage reporting, model state, and performance checks. It selects a model profile or a direct provider, configures the connection, and hands control to Claude Code. The selected upstream service supplies inference.

| Entry point | Responsibility |
| --- | --- |
| [`alt-claude`](../alt-claude) | Routes help, profile listing, usage, policy, and offline compaction. Dispatches `--profile` and direct provider calls. |
| [`alt-claude-profile`](../alt-claude-profile) | Loads the profile, checks project policy and resume size, and handles OpenRouter free-route preflight and fallback. |
| [`alt-claude-core`](../alt-claude-core) | Configures provider credentials, endpoints, and local proxies. Maps `--yolo` and forwards Claude Code arguments. |
| [`install.sh`](../install.sh) | Installs the launcher and helpers and generates compatibility commands from `profiles/*.env`. |

A profile launch checks whether the model is enabled and checks the selected profile against project policy before network activity. It then checks the local transcript when an explicit resume ID is available. An eligible OpenRouter free route runs a minimal preflight unless the daily quota marker is already current. Normal launches and fallback launches both return through the public CLI for the direct provider check before entering the core.

The policy helper reads `.alt-claude/config` at the Git root, or in the current directory outside a Git worktree. The session compactor reads local Claude Code JSONL and can write a Markdown handoff for a fresh session. The usage helper checks credentials and quota information exposed by configured providers. The model state helper tracks the last model per project, ratings, and globally disabled models. The performance helper ranks enabled free profiles using short live inference tests.

```bash
alt-claude profiles
alt-claude policy show
alt-claude --profile north-mini-code
alt-claude --use codex
alt-claude compact SESSION_ID
```

See [Providers](providers.md) for backend requirements, [Credentials](credentials.md) for local authentication, and [Limits](limits.md) for known boundaries.
