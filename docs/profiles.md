# Model profiles

`alt-claude` keeps provider/authentication logic in one place. Model shortcuts are declarative files under `profiles/`.

Each profile defines:

```bash
PROVIDER=openrouter
MODEL=vendor/model:free
DISPLAY_NAME="Readable name"
STATUS=active
NOTES="Operational note"
```

`./install.sh` copies the profiles to the user data directory and generates `alt-claude-<profile>` launchers in the install directory.

## Common flags

Generated launchers do not implement their own parser. They forward everything to the core launcher:

```bash
alt-claude-laguna --yolo
alt-claude-nemotron --resume SESSION_ID
alt-claude-nex-pro --yolo --resume SESSION_ID
```

This guarantees that `--yolo`, `--resume` and future Claude Code flags behave consistently across all variants.

## Current profiles

Active:

- `laguna` — Poolside Laguna S 2.1 (free)
- `nemotron` — NVIDIA Nemotron 3 Ultra (free)
- `north-mini-code` — Cohere North Mini Code (free)

Experimental:

- `laguna-xs` — Poolside Laguna XS 2.1 (free)
- `nemotron-lightning` — NVIDIA Nemotron 3.5 Lightning (free)
- `nex-pro` — Nex AGI Nex-N2.5-Pro (free)
- `nex-mini` — Nex AGI Nex-N2.5-Mini (free)
- `inkling-small` — Thinking Machines Inkling Small (free)
- `free` — OpenRouter dynamic free-model router

Experimental means the integration is wired but still needs real repository tasks before being promoted to `active`.

## Validation

Validate all OpenRouter model IDs and zero-price status without spending inference tokens:

```bash
bash tools/check-profiles.sh
```

A missing model or a model whose prompt/completion price is no longer zero causes a non-zero exit status.

## Adding a profile

Add one `.env` file to `profiles/` and rerun `./install.sh`. No new parser or wrapper implementation should be added.

Free endpoints can disappear, become rate-limited, or change data-retention terms. Treat the model catalog as operational configuration, not a permanent guarantee.
