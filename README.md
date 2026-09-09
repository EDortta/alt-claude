# alt-claude

Unified launcher for running Claude Code against alternative model providers and gateways.

`alt-claude` keeps the Claude Code interface while selecting the backend with `--use`.

## Current providers

- `copilot` — GitHub Copilot through `copilot-api`
- `codex` — OpenAI Codex through `claude-codex-proxy`
- `openrouter` — OpenRouter Anthropic-compatible endpoint
- `kimi` — Kimi Anthropic-compatible endpoint
- `grok` — credential health check; direct Claude Code use is currently disabled in the launcher
- `nvidia` — credential health check; direct Claude Code use requires an Anthropic-compatible NIM endpoint or bridge

## Install

```bash
git clone git@github.com:EDortta/alt-claude.git
cd alt-claude
./install.sh
```

The installer places `alt-claude` and the included `alt-claude-*` shortcuts at
`~/.local/bin/`. To use another destination, set `ALT_CLAUDE_INSTALL_DIR`:

```bash
ALT_CLAUDE_INSTALL_DIR="$HOME/bin" ./install.sh
```

## Basic usage

```bash
alt-claude --use copilot
alt-claude --use codex --yolo
alt-claude --use openrouter --model <provider/model>
alt-claude --use kimi --yolo
```

`--user` is accepted as a compatibility alias for `--use`.

Any unrecognized option is forwarded to Claude Code, so normal Claude arguments such as `--resume` continue to work.

## Provider and credential health

```bash
alt-claude --usage
```

This scans the configured providers, checks whether credentials are accepted, and reports usage where the provider exposes it through its API.

Example:

```text
PROVEDOR     STATUS       USO MÊS           DETALHE
------------ ------------ ------------------ ----------------------------------------
copilot      OK           N/D                autenticação local configurada
codex        OK           N/D                conta(s) configurada(s)
openrouter   OK           US$ 0.0000         total=US$ 0.0000, limite restante=N/D
kimi         HTTP 401     -                  chave inválida/expirada ou conta incorreta
grok         OK           N/D                uso histórico exige xAI Management API
nvidia       OK           N/D                API pública não expõe uso por chave
```

## Credentials

Default credential root:

```text
~/.config/credentials/personal/ai/
```

Expected files:

```text
openrouter.env
kimi.env
grok.env
nvidia.env
copilot.env
```

Keep them private:

```bash
chmod 700 ~/.config/credentials/personal/ai
chmod 600 ~/.config/credentials/personal/ai/*.env
```

See [docs/credentials.md](docs/credentials.md), [docs/providers.md](docs/providers.md), and [docs/usage.md](docs/usage.md).

## Design principles

- one launcher, not one script per provider;
- credentials live outside the repository;
- Claude Code remains the user-facing harness;
- provider-specific logic stays isolated;
- health checks should not require an inference call when a non-billable endpoint exists;
- never invent usage data when a provider does not expose it.
