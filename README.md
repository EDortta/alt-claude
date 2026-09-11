# alt-claude

Unified launcher for running Claude Code against alternative providers and model profiles.

The project has two layers:

- `alt-claude` handles providers, credentials and Claude Code integration;
- `alt-claude-*` launchers are generated from declarative files in `profiles/`.

That keeps `--yolo`, `--resume` and every future common flag consistent across all model shortcuts.

## Install

```bash
git clone git@github.com:EDortta/alt-claude.git
cd alt-claude
./install.sh
```

Default locations:

```text
~/.local/bin/alt-claude
~/.local/bin/alt-claude-profile
~/.local/bin/alt-claude-*
~/.local/share/alt-claude/profiles/*.env
```

Override with:

```bash
ALT_CLAUDE_INSTALL_DIR="$HOME/bin" \
ALT_CLAUDE_DATA_DIR="$HOME/.local/share/alt-claude" \
./install.sh
```

## Common flags

Every generated `alt-claude-*` forwards its arguments to the same core launcher.

```bash
alt-claude-laguna --yolo
alt-claude-nemotron --resume SESSION_ID
alt-claude-north-mini-code --yolo --resume SESSION_ID
```

`--yolo` is translated by `alt-claude` to Claude Code's `--dangerously-skip-permissions`.

`--resume SESSION_ID` is forwarded unchanged to Claude Code. Other unknown Claude Code options are forwarded as well.

Use `--yolo` only in repositories and environments where autonomous command execution is acceptable.

## Model profiles

Active profiles:

```text
alt-claude-laguna
alt-claude-nemotron
alt-claude-north-mini-code
```

Experimental/free profiles:

```text
alt-claude-laguna-xs
alt-claude-nemotron-lightning
alt-claude-nex-pro
alt-claude-nex-mini
alt-claude-inkling-small
alt-claude-free
```

The named free profiles currently try OpenRouter first. Before Claude Code starts, `alt-claude-profile` performs a one-token free preflight against the selected model. If OpenRouter rejects the request because the free route is unavailable, rate-limited or requires credit, the launcher falls back to already-configured subscription providers in this order:

```text
codex -> copilot
```

The fallback is explicit on stderr and never silently switches to a paid API key. The selected model necessarily changes when fallback happens, but `--yolo`, `--resume` and other Claude Code arguments are preserved.

To disable automatic fallback for diagnostics:

```bash
ALT_CLAUDE_NO_FALLBACK=1 alt-claude-nemotron --yolo
```

The generic free route:

```bash
alt-claude-free --yolo
```

uses `openrouter/free` when the free route is available and otherwise follows the same fallback policy.

Free model availability, quotas and routing can change without notice.

## Adding another model shortcut

Create only one file:

```text
profiles/my-model.env
```

Example:

```bash
PROVIDER=openrouter
MODEL=vendor/model:free
DISPLAY_NAME="My Model"
STATUS=experimental
NOTES="Short operational note"
```

Then run:

```bash
./install.sh
```

The installer generates `alt-claude-my-model`. No new argument parser or provider wrapper is required.

Validate the OpenRouter catalog and zero-price status without running inference:

```bash
bash tools/check-profiles.sh
```

## Direct provider usage

```bash
alt-claude --use copilot
alt-claude --use codex --yolo
alt-claude --use openrouter --model <provider/model>
alt-claude --use kimi
```

`--user` remains accepted as a compatibility alias for `--use`.

## Provider and credential health

```bash
alt-claude --usage
```

This checks configured credentials and reports usage where the provider exposes it through its API.

## Credentials

Default credential root:

```text
~/.config/credentials/personal/ai/
```

Typical files:

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

## Tests

```bash
bash tests/test-profiles.sh
bash tools/check-profiles.sh
```

The structural test verifies profile installation, exact forwarding of `--yolo` and `--resume`, and the OpenRouter-free-to-Codex fallback path. The catalog check verifies that OpenRouter model IDs still exist and are still zero-cost.

See also [docs/credentials.md](docs/credentials.md), [docs/providers.md](docs/providers.md), [docs/profiles.md](docs/profiles.md), and [docs/usage.md](docs/usage.md).

## Design principles

- one execution core;
- model variants are data, not copied scripts;
- credentials stay outside the repository;
- Claude Code remains the user-facing harness;
- common flags are inherited automatically by every profile;
- free aliases never fall silently into pay-as-you-go APIs;
- provider/model health data must not be invented when an API does not expose it.
