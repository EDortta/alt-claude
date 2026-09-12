# alt-claude

Unified Claude Code launcher for alternative providers and model profiles.

The preferred interface is one command:

```bash
alt-claude --profile north-mini-code --yolo
alt-claude --profile nemotron --resume SESSION_ID
alt-claude profiles
alt-claude compact SESSION_ID
alt-claude policy show
```

Compatibility launchers such as `alt-claude-north-mini-code` remain installed and delegate to the same core.

## Help

The CLI has one complete top-level help:

```bash
alt-claude --help
```

Contextual help is also available:

```bash
alt-claude help profiles
alt-claude help compact
alt-claude help policy
alt-claude help providers
```

The main help documents profiles, providers, `--yolo`, `--resume`, usage checks, context guard, offline compaction, free-route fallback, privacy classes and project policy.

## Install

```bash
git clone git@github.com:EDortta/alt-claude.git
cd alt-claude
./install.sh
```

The installer places the dispatcher, provider core, profile dispatcher, offline session compactor and policy helper under `~/.local/bin/`, and copies declarative profiles to `~/.local/share/alt-claude/profiles/`.

## Common flags

All profiles share the same flag path:

```bash
alt-claude --profile north-mini-code --yolo
alt-claude --profile north-mini-code --resume SESSION_ID
alt-claude --profile north-mini-code --yolo --resume SESSION_ID
```

`--yolo` becomes Claude Code's `--dangerously-skip-permissions`. `--resume` and unknown Claude Code flags are forwarded unchanged.

## Privacy classes

Every profile must explicitly declare one of:

```text
PRIVACY=sensitive_ok
PRIVACY=review
PRIVACY=public_only
```

Meaning:

- `sensitive_ok`: the profile is approved by the alt-claude policy metadata for sensitive projects;
- `review`: routing/provider terms must be reviewed before private or sensitive code is sent;
- `public_only`: do not use with private or sensitive source code.

`alt-claude profiles` renders these as visibly separated groups, with `public_only` models under a clear **DO NOT USE WITH SENSITIVE/PRIVATE CODE** section.

No free OpenRouter profile is promoted to `sensitive_ok` merely because it works technically. Unknown or unverified privacy behavior is classified conservatively as `review`.

The dynamic `openrouter/free` route and the free Thinking Machines Inkling profiles are currently `public_only`.

## Project policy

Projects can block models/providers before any request leaves the machine. Configuration lives at:

```text
<git-root>/.alt-claude/config
```

The file is declarative data and is never executed with `source`, `eval` or equivalent.

Create a normal policy:

```bash
alt-claude policy init standard
```

Create a restrictive policy for confidential code:

```bash
alt-claude policy init sensitive
```

Inspect it:

```bash
alt-claude policy show
```

Block a specific profile or provider:

```bash
alt-claude policy deny profile inkling
alt-claude policy deny provider openrouter
```

Explicitly allow one profile when you have reviewed its terms:

```bash
alt-claude policy allow profile north-mini-code
```

A sensitive policy defaults to rejecting both `review` and `public_only`. Policy rejection happens before the OpenRouter preflight or model call.

Example generated config:

```text
mode=sensitive
deny_profiles=
allow_profiles=
deny_providers=
deny_privacy=review,public_only
```

## Context guard

Each model profile declares:

```text
CONTEXT_WINDOW
SAFE_CONTEXT_TOKENS
AUTO_COMPACT_PCT
```

`AUTO_COMPACT_PCT` is exported through `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` as a best-effort early-compaction hint. Because Claude Code versions can change how auto-compaction behaves, `alt-claude` also has a deterministic guard for `--resume`.

Before resuming a known local session, the launcher reads its JSONL transcript offline. If the latest observed context is already beyond the profile's safe threshold, it refuses a request likely to fail at the provider and tells you to create a handoff instead.

For example, North Mini Code uses:

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

When `/compact` can no longer fit inside the model's context, generate a new-session handoff locally:

```bash
alt-claude compact SESSION_ID
```

It reads Claude Code's local session JSONL, makes no model/API call, and writes:

```text
claude-handoff-SESSION_ID.md
```

Then start fresh, for example:

```bash
alt-claude --profile north-mini-code --yolo \
  "Leia claude-handoff-SESSION_ID.md, confira o estado atual do repositório e continue o trabalho."
```

## Profiles

List installed profiles, privacy groups and context budgets:

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

Experimental means the integration is wired but still needs repeated real software-engineering tasks before promotion to active.

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

The check compares each OpenRouter profile with the live catalog and reports whether the model still exists, remains free, its current API context length, the declared context length and safe threshold.

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

The structural suite covers complete help, installation, unified dispatch, privacy metadata, project policy, `--yolo`, `--resume`, free fallback, oversized-session blocking and offline handoff generation.

## Design principles

- one user-facing command and one provider execution core;
- model variants are declarative data;
- privacy metadata is explicit, never inferred from a model name;
- sensitive-project restrictions are enforced before network calls;
- project policy files are data, never executable shell;
- common flags and context policy are inherited by every profile;
- credentials remain outside the repository;
- free aliases never silently fall into pay-as-you-go APIs;
- context limits are validated against live catalog data;
- recovery from an oversized session must remain possible without another model call.
