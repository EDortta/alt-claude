# Providers

`alt-claude` keeps provider/authentication concerns separate from model profiles.

Current provider adapters:

- `copilot` — GitHub Copilot through `copilot-api`;
- `codex` — OpenAI Codex through `claude-codex-proxy`;
- `openrouter` — Anthropic-compatible OpenRouter endpoint;
- `kimi` — Anthropic-compatible Kimi endpoint when a valid Kimi Code key is available;
- `grok` — xAI API through a local Anthropic-compatible bridge (`alt-claude-grok-bridge`), keeping Claude Code as the console;
- `nvidia` — credential health check; direct use requires an Anthropic-compatible NIM endpoint or a bridge.

Model-specific shortcuts do not add provider logic. They declare `PROVIDER` and `MODEL` in `profiles/*.env` and delegate to the core launcher.

For OpenRouter model aliases and their lifecycle, see [profiles.md](profiles.md).


## Grok bridge

The Grok adapter starts a localhost bridge (default port 8787) that accepts the Anthropic Messages shape used by Claude Code and translates it to xAI's OpenAI-compatible Chat Completions API. The bridge handles text, Claude tool definitions, tool calls/tool results, non-streaming responses and a synthesized Anthropic SSE stream for Claude Code.

The default `grok` profile uses `grok-build-0.1` because it is the lower-cost coding-oriented xAI model. Override it explicitly when needed:

```bash
alt-claude-grok --model grok-4.7
```

The public xAI API is pay-as-you-go. Grok is therefore never inserted into the automatic free-provider fallback chain.
