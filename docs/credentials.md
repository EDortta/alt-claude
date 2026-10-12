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
groq.env
cohere.env
google.env
freeinference.env
aihubmix.env
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

## First direct free-provider block

```bash
# groq.env
GROQ_API_KEY="..."
```

```bash
# cohere.env
COHERE_API_KEY="..."
```

```bash
# google.env
GOOGLE_AI_STUDIO_API_KEY="..."
# GEMINI_API_KEY is also accepted.
```

```bash
# nvidia.env
NVIDIA_NIM_API_KEY="..."
# NVIDIA_API_KEY is also accepted.
```

```bash
# freeinference.env
FREEINFERENCE_API_KEY="..."
```

```bash
# aihubmix.env
AIHUBMIX_API_KEY="..."
```

Kilo's anonymous free lane does not require a credential file.
