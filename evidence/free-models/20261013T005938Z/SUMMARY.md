# alt-claude free-model evidence

run: 20261013T005938Z
git: f5709e2d641d683efab8fcceda6d51c8b7d2d8f4
branch: development
profiles tested: 22
cost policy: free profiles only; fallback disabled
project policy: ignored only for diagnostic probe

| # | Profile | Provider | Model | Score | Seconds | Status |
|---:|---|---|---|---:|---:|---|
| 1 | nemotron-lightning | openrouter | nvidia/nemotron-3.5-lightning:free | 3/3 | 6.087 | ok |
| 2 | nemotron-super | openrouter | nvidia/nemotron-3-super-120b-a12b:free | 3/3 | 7.270 | ok |
| 3 | kilo-north-mini-code | kilo | cohere/north-mini-code:free | 3/3 | 7.981 | ok |
| 4 | dots3-note | openrouter | dots-studio/dots-3-note-preview:free | 3/3 | 12.899 | ok |
| 5 | nemotron | openrouter | nvidia/nemotron-3-ultra-550b-a55b:free | 3/3 | 28.966 | ok |
| 6 | laguna | openrouter | poolside/laguna-s-2.1:free | 2/3 | 6.574 | partial-2/3 |
| 7 | aihubmix-glm-5.3-flash | aihubmix | coding-glm-5.3-flash-free | - | 0.094 | credential-missing |
| 8 | cohere-north-mini-code | cohere | north-mini-code-1-0 | - | 0.094 | credential-missing |
| 9 | groq-gpt-oss-120b | groq | openai/gpt-oss-120b | - | 0.095 | credential-missing |
| 10 | freeinference-glm-5.3-flash | freeinference | glm-5.3-flash | - | 0.097 | credential-missing |
| 11 | google-gemini-3.8-flash | google | gemini-3.8-flash | - | 0.130 | credential-missing |
| 12 | glm-5.3-flash | openrouter | z-ai/glm-5.3-flash:free | - | 0.306 | provider-unavailable |
| 13 | ling-flash-fin | openrouter | inclusionai/ling-3.0-flash-fin:free | - | 0.310 | provider-unavailable |
| 14 | nex-pro | openrouter | nex-agi/nex-n2.5-pro:free | - | 0.310 | provider-unavailable |
| 15 | nex-mini | openrouter | nex-agi/nex-n2.5-mini:free | - | 0.320 | provider-unavailable |
| 16 | inkling-small | openrouter | thinkingmachines/inkling-small:free | - | 0.325 | provider-unavailable |
| 17 | inkling | openrouter | thinkingmachines/inkling:free | - | 0.348 | provider-unavailable |
| 18 | deepseek-v4-flash | openrouter | deepseek/deepseek-v4-flash:free | - | 0.488 | provider-unavailable |
| 19 | laguna-xs | openrouter | poolside/laguna-xs-2.1:free | - | 0.492 | provider-unavailable |
| 20 | north-mini-code | openrouter | cohere/north-mini-code:free | - | 4.620 | response |
| 21 | free | openrouter | openrouter/free | - | 18.860 | response |
| 22 | nvidia-deepseek-v4.1-flash | nvidia | deepseek-ai/deepseek-v4.1-flash | - | 60.059 | timeout |
