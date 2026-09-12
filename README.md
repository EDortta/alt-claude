# alt-claude

Unified Claude Code launcher for alternative providers and model profiles.

The preferred interface is now a single command:

```bash
alt-claude --profile north-mini-code --yolo
alt-claude --profile nemotron --resume SESSION_ID
alt-claude profiles
alt-claude compact SESSION_ID
```

Compatibility launchers such as `alt-claude-north-mini-code` remain installed and simply delegate to the same core.

## Install

```bash
git clone git@github.com:EDortta/alt-claude.git
cd alt-claude
./install.sh
```

The installer places the dispatcher, provider core, profile dispatcher and offline session compactor under `~/.local/bin/`, and copies declarative profiles to `~/.local/share/alt-claude/profiles/`.

## Common flags

All profiles share the same flag path:

```bash
alt-claude --profile north-mini-code --yolo
alt-claude --profile north-mini-code --resume SESSION_ID
alt-claude --profile north-mini-code --yolo --resume SESSION_ID
```

`--yolo` becomes Claude Code's `--dangerously-skip-permissions`. `--resume` and unknown Claude Code flags are forwarded unchanged.

## Context guard

Each model profile declares:

```text
CONTEXT_WINDOW
SAFE_CONTEXT_TOKENS
AUTO_COMPACT_PCT
```

`AUTO_COMPACT_PCT` is exported through `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` as a best-effort early-compaction hint. Because Claude Code versions can change how auto-compaction behaves, `alt-claude` also has a deterministic guard for `--resume`.

Before resuming a known local session, the launcher reads its JSONL transcript offline. If the latest observed context is already beyond the profile's safe threshold, it refuses a request that is likely to fail at the provider and tells you to create a handoff instead.

For example, North Mini Code uses a 256K window but reserves substantial space for tools and output:

```text
CONTEXT_WINDOW=256000
SAFE_CONTEXT_TOKENS=180000
AUTO_COMPACT_PCT=65
```

To bypass the guard deliberately:

```bash
ALT_CLAUDE_ALLOW_OVERSIZE_RESUME=1 alt-claude --profile north-mini-code --resume SESSION_ID
```

## Offline session compact / recovery

When `/compact` can no longer fit inside the model's own context, generate a new-session handoff locally:

```bash
alt-claude compact SESSION_ID
```

It reads Claude Code's local session JSONL, makes no model/API call, and writes:

```text
claude-handoff-SESSION_ID.md
```

The handoff contains available repository metadata, frequently touched files, recent shell commands, recent dialogue and a continuation instruction. It is intentionally a lossy recovery artifact, not an LLM semantic summary; the current repository/filesystem remains authoritative.

Then start fresh, for example:

```bash
alt-claude --profile north-mini-code --yolo \
  "Leia claude-handoff-SESSION_ID.md, confira o estado atual do repositório e continue o trabalho."
```

You can inspect the locally observed context without generating a handoff:

```bash
alt-claude-session-compact SESSION_ID --status
```

## Profiles

List the installed catalog and its context budgets:

```bash
alt-claude profiles
```

Current active profiles include:

```text
north-mini-code
laguna
nemotron
```

Additional experimental profiles include:

```text
laguna-xs
nemotron-lightning
nex-pro
nex-mini
inkling-small
inkling
deepseek-v4-flash
glm-5.3-flash
free
```

The experimental models are deliberately not promoted to active merely because their endpoints exist; they still need repeated real software-engineering tasks.

The free Thinking Machines Inkling endpoints may have data-retention/model-improvement terms different from ordinary paid endpoints. Review those terms before sending private source code.

## Free-route fallback

Named free profiles try OpenRouter first. A minimal preflight detects exhausted/blocked free routes. If unavailable, `alt-claude` falls back explicitly to already-configured subscription providers:

```text
codex -> copilot
```

The fallback is announced and never silently selects a pay-as-you-go API. The model necessarily changes, while `--yolo`, `--resume` and other Claude arguments are preserved.

Disable fallback for diagnosis:

```bash
ALT_CLAUDE_NO_FALLBACK=1 alt-claude --profile north-mini-code --yolo
```

## Live profile validation

Run:

```bash
bash tools/check-profiles.sh
```

The check compares each OpenRouter profile with the live catalog and reports whether the model still exists, remains free, its current API context length, the declared context length and the safe threshold. It fails on price changes or unsafe/context-drift configuration.

## Direct provider mode

The original provider interface remains available:

```bash
alt-claude --use copilot
alt-claude --use codex --yolo
alt-claude --use openrouter --model <provider/model>
alt-claude --usage
```

`--user` remains accepted as a compatibility alias for `--use`.

## Credentials

Default root:

```text
~/.config/credentials/personal/ai/
```

Keep credentials private:

```bash
chmod 700 ~/.config/credentials/personal/ai
chmod 600 ~/.config/credentials/personal/ai/*.env
```

See [docs/credentials.md](docs/credentials.md), [docs/providers.md](docs/providers.md), [docs/profiles.md](docs/profiles.md), and [docs/usage.md](docs/usage.md).

## Tests

```bash
bash tests/test-profiles.sh
bash tools/check-profiles.sh
```

The structural suite covers installation, unified dispatch, `--yolo`, `--resume`, OpenRouter-free fallback, oversized-session blocking and offline handoff generation.

## Design principles

- one user-facing command and one provider execution core;
- model variants are declarative data;
- common flags and context policy are inherited by every profile;
- credentials remain outside the repository;
- free aliases never silently fall into pay-as-you-go APIs;
- context limits are validated against live catalog data;
- recovery from an oversized session must remain possible without another model call.
