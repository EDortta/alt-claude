# Usage and health checks

## Launching Claude Code

```bash
alt-claude --use copilot
alt-claude --use codex --yolo
alt-claude --use openrouter --model <provider/model>
alt-claude --use kimi --resume <session-id>
```

`--yolo` is translated to Claude Code's:

```text
--dangerously-skip-permissions
```

`--user` is accepted as a compatibility alias for `--use`.

All other arguments are forwarded to Claude Code.

## Health and usage report

```bash
alt-claude --usage
```

The report has two goals:

1. verify whether configured credentials are accepted;
2. show usage where the provider exposes it through the available API.

The report does not invent usage values. `N/D` means the provider does not expose the requested metric through the credential/API path currently configured.

### OpenRouter

Checks `/api/v1/key` and reports monthly/total usage when available.

### Kimi

Checks the native Anthropic Messages endpoint with a one-token request. Interpretations:

```text
200  key accepted
401  invalid/expired key or wrong Kimi product
403  recognized credential without required access/plan
429  credential accepted, but quota/rate limit reached
```

This health check can consume a negligible inference request because Kimi does not provide the same zero-inference key-status endpoint used by OpenRouter.

### Grok

Checks `/v1/models` to validate the key. Historical usage requires xAI Management API credentials and is therefore reported as `N/D` by default.

### NVIDIA

Checks the NVIDIA API Catalog model endpoint. Usage by key is not exposed by that path, so only credential health is reported.

### Copilot and Codex

Reports whether the local authentication/gateway configuration is present. Provider-plan consumption is not currently normalized by `alt-claude`.
