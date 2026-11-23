# Limits

| Area | Current behavior |
| --- | --- |
| Provider support | Copilot and Codex launches depend on their local proxies and authentication. OpenRouter and Kimi use Anthropic-compatible endpoints. Grok and NVIDIA have credential checks only in the current launcher. |
| Free-route availability | Catalog entries, context limits, and zero pricing can change. A successful startup preflight cannot guarantee quota or availability later in the session. |
| Fallback | Fallback runs at launch. The default preference is Codex, then Copilot, based on local command availability. Once the launcher hands off to a fallback, a subsequent failure does not trigger another fallback. An in-session OpenRouter 429 requires a relaunch for fallback to be considered. |
| Daily quota | A recognized OpenRouter daily free quota response is cached locally through the current UTC date. `ALT_CLAUDE_NO_FALLBACK=1` skips the preflight and fallback selection. |
| Resume guard | The guard uses the latest recorded usage in a local transcript and the selected profile's safe threshold. Missing usage, a missing transcript, or unavailable helper dependencies leave the launch unblocked. This estimate cannot account for the next prompt, tools, or output. |
| Auto-compaction | `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` is a best-effort hint to Claude Code. `alt-claude compact SESSION_ID` produces a local Markdown handoff for a fresh session and leaves the original transcript intact. |
| Auto mode | Copilot, Codex, and OpenRouter force `CLAUDE_CODE_AUTO_MODE_SERVER=0` in the current core, overriding an inherited value. Client-side classifier requests consume normal provider quota. |
| Permissions | `--yolo` maps to Claude Code's `--dangerously-skip-permissions`. |
| Policy coverage | Profile launches check the declared privacy class when the policy helper and Python are available. Direct `--use` calls check the explicit provider against policy using `sensitive_ok`, so they do not evaluate the selected model's privacy class. Set provider denies explicitly when a project must block direct routing to a provider. |
| Privacy metadata | The classes govern launcher policy. Provider routing, retention, and model-improvement terms require separate review. A local handoff can contain excerpts from the original session. |

For hardware-specific throughput and task-sizing limits, see [Local worker capacity](local-worker-capacity.md).
