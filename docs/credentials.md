# Credentials

`alt-claude` does not store secrets in the repository.

Default directory:

```text
~/.config/credentials/personal/ai/
```

Override it with:

```bash
export ALT_CLAUDE_CREDENTIALS_DIR=/custom/path
```

Expected files:

```text
copilot.env
openrouter.env
kimi.env
grok.env
nvidia.env
```

Examples:

```bash
# openrouter.env
OPENROUTER_API_KEY="..."
```

```bash
# kimi.env
KIMI_API_KEY="..."
```

```bash
# grok.env
GROK_API_KEY="..."
# XAI_API_KEY is also accepted instead of GROK_API_KEY.
GROK_MODEL="grok-build-0.1"
GROK_REASONING_EFFORT="low"
```

```bash
# nvidia.env
NVIDIA_API_KEY="..."
```

For Copilot, `copilot.env` can define `COPILOT_API_HOME`. Authentication data itself may live under:

```text
~/.config/credentials/personal/ai/copilot-api/
```

or the legacy path:

```text
~/.local/share/copilot-api/
```

Recommended permissions:

```bash
chmod 700 ~/.config/credentials/personal/ai
chmod 600 ~/.config/credentials/personal/ai/*.env
```

Never commit these files.
