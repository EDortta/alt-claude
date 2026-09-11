# Usage and health checks

## Core launcher

```bash
alt-claude --use copilot
alt-claude --use codex --yolo
alt-claude --use openrouter --model vendor/model
```

Unknown Claude Code options are forwarded unchanged.

## Common flags on model shortcuts

Every generated `alt-claude-*` launcher uses the same core parser:

```bash
alt-claude-laguna --yolo
alt-claude-nemotron --resume SESSION_ID
alt-claude-nex-pro --yolo --resume SESSION_ID
```

`--yolo` maps to Claude Code's `--dangerously-skip-permissions`.

`--resume SESSION_ID` is forwarded to Claude Code so an existing session can be continued.

## Provider/key health

```bash
alt-claude --usage
```

This checks configured provider credentials and reports usage where an API exposes it.

## Model catalog health

```bash
bash tools/check-profiles.sh
```

This checks OpenRouter profiles without running inference. It verifies that each model ID exists and that prompt/completion pricing is still zero for profiles intended to be free.

Free endpoints can be rate-limited or removed even when a profile was valid previously.
