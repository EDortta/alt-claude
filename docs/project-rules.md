# Project rules

## CLI and profiles

- Keep `alt-claude` as the public entry point and provider execution in [`alt-claude-core`](../alt-claude-core). Generate compatibility launchers through [the installer](../install.sh).
- Add model variants as `profiles/*.env` files. Declare the provider, model, lifecycle status, privacy class, context window, safe resume threshold, and auto-compaction percentage. Use only trusted profile files because Bash sources them.
- Preserve forwarding for `--resume` and Claude Code options. Keep the `--yolo` mapping in the shared core and keep help consistent with behavior.
- Promote an experimental profile only after repeated real repository work. Recheck live catalog availability, price, and context when changing free OpenRouter profiles.

## Policy, credentials, and recovery

- Treat `.alt-claude/config` as plain key-value data. Keep project policy checks ahead of provider traffic. Explicit profile and provider denies take precedence over a profile allow, which can override privacy-class restrictions.
- Declare one privacy class for each profile. Use `review` for unverified routing or terms. Assign `sensitive_ok` only after reviewing the route and its terms. Keep `openrouter/free` and the free Inkling profiles `public_only`.
- Keep tokens, provider credentials, session transcripts, and sensitive handoffs out of commits. Use [the credential directory](credentials.md) for provider authentication.
- Fail closed on unavailable OpenRouter free routes by default. Require explicit opt-in for fallback to configured subscription routes, announce the selected fallback, and preserve the user's Claude Code arguments.
- Keep handoff generation offline and preserve the source transcript.

## Validation

Run the structural suite from the repository root after changing the launcher, installer, policy, or session helpers.

```bash
bash tests/test-profiles.sh
```

Run the live catalog check when changing OpenRouter profile IDs, pricing expectations, or context declarations. It requires network access and checks the catalog without running inference.

```bash
bash tools/check-profiles.sh
```

When behavior changes, update the CLI help and the relevant existing reference in [Required reading](required-reading.md).
