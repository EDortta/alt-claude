# Providers

## Copilot

Uses `@jeffreycao/copilot-api` as a local Anthropic-compatible gateway.

```bash
alt-claude --use copilot --yolo
```

## Codex

Uses `claude-codex-proxy` as a local Anthropic-compatible gateway.

```bash
alt-claude --use codex --yolo
```

## OpenRouter

Uses the Anthropic-compatible OpenRouter endpoint directly.

```bash
alt-claude --use openrouter --model <provider/model>
```

This is the preferred path for experimenting with free or low-cost models because the provider/model can be changed without changing Claude Code.

## Kimi

Uses Kimi's native Anthropic Messages-compatible endpoint:

```text
https://api.kimi.com/coding/
```

```bash
alt-claude --use kimi
```

The API key must belong to Kimi Code access. A normal Kimi/Open Platform key may return HTTP 401 on the coding endpoint. The default model is `k3`.

## Grok / xAI

The key can be health-checked with `alt-claude --usage`, but direct Claude Code launch is intentionally disabled because the xAI API path used here is not treated as a drop-in Anthropic Messages endpoint.

Use Grok through OpenRouter or add an explicit bridge.

## NVIDIA

`NVIDIA_API_KEY` can be validated against the NVIDIA API Catalog. The catalog endpoint is OpenAI-compatible, so the launcher does not pretend it is directly usable by Claude Code.

Direct launch becomes available when `nvidia.env` provides an Anthropic-compatible NIM or bridge:

```bash
NVIDIA_API_KEY="..."
NVIDIA_ANTHROPIC_BASE_URL="http://host:8000"
NVIDIA_MODEL="publisher/model"
```

Then:

```bash
alt-claude --use nvidia --yolo
```
