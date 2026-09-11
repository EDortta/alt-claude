# Providers

`alt-claude` keeps provider/authentication concerns separate from model profiles.

Current provider adapters:

- `copilot` — GitHub Copilot through `copilot-api`;
- `codex` — OpenAI Codex through `claude-codex-proxy`;
- `openrouter` — Anthropic-compatible OpenRouter endpoint;
- `kimi` — Anthropic-compatible Kimi endpoint when a valid Kimi Code key is available;
- `grok` — credential health check; direct Claude Code path is intentionally disabled until a supported Anthropic-compatible route is available;
- `nvidia` — credential health check; direct use requires an Anthropic-compatible NIM endpoint or a bridge.

Model-specific shortcuts do not add provider logic. They declare `PROVIDER` and `MODEL` in `profiles/*.env` and delegate to the core launcher.

For OpenRouter model aliases and their lifecycle, see [profiles.md](profiles.md).
