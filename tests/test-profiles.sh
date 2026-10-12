#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BIN_DIR="$TMP/bin"
DATA_DIR="$TMP/data"
CAPTURE="$TMP/args.txt"
CREDS="$TMP/credentials"
TEST_HOME="$TMP/home"
mkdir -p "$BIN_DIR" "$DATA_DIR" "$CREDS" "$TEST_HOME"

python3 -m py_compile "$ROOT/tools/session-compact.py" "$ROOT/tools/project-policy.py" "$ROOT/tools/model-state.py" "$ROOT/tools/performance.py" "$ROOT/tools/xai-anthropic-bridge.py" "$ROOT/tools/openai-anthropic-bridge.py"

cat >"$TMP/fake-alt-claude" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"${ALT_CLAUDE_TEST_CAPTURE:?}"
EOF
chmod +x "$TMP/fake-alt-claude"

PATH="$BIN_DIR:$PATH" ALT_CLAUDE_INSTALL_DIR="$BIN_DIR" ALT_CLAUDE_DATA_DIR="$DATA_DIR" bash "$ROOT/install.sh" >/dev/null

# Unified help must cover the whole product, not just the legacy core.
help="$($BIN_DIR/alt-claude --help)"
grep -q 'OPÇÕES COMUNS' <<<"$help"
grep -q 'POLÍTICA POR PROJETO' <<<"$help"
grep -q 'CONTEXTO E COMPACTAÇÃO' <<<"$help"
grep -q 'AJUDA POR ASSUNTO' <<<"$help"
grep -q -- '--list-performance' <<<"$help"
$BIN_DIR/alt-claude help performance | grep -q 'microtestes determinísticos'
$BIN_DIR/alt-claude help policy | grep -q 'policy init sensitive'
$BIN_DIR/alt-claude help compact | grep -q 'handoff Markdown OFFLINE'

# Normal forwarding: a healthy free route stays on the requested free model.
printf 'OPENROUTER_API_KEY=test-key\n' >"$CREDS/openrouter.env"
cat >"$TMP/curl" <<'EOF'
#!/usr/bin/env bash
out=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o) out="$2"; shift 2 ;;
        -w) shift 2 ;;
        *) shift ;;
    esac
done
[[ -n "$out" ]] && printf '%s\n' '{"choices":[{"message":{"content":"OK"}}]}' >"$out"
printf '200'
EOF
chmod +x "$TMP/curl"

PATH="$TMP:$PATH" \
ALT_CLAUDE_BIN="$TMP/fake-alt-claude" \
ALT_CLAUDE_TEST_CAPTURE="$CAPTURE" \
ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" \
ALT_CLAUDE_CREDENTIALS_DIR="$CREDS" \
    "$BIN_DIR/alt-claude-laguna" --yolo --resume session-123

expected=$(cat <<'EOF'
--use
openrouter
--model
poolside/laguna-s-2.1:free
--yolo
--resume
session-123
EOF
)
actual="$(cat "$CAPTURE")"
[[ "$actual" == "$expected" ]] || { echo "Falha no forwarding" >&2; diff -u <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") || true; exit 1; }

# A free profile must fail closed by default: no implicit Codex/Copilot fallback.
cat >"$TMP/curl" <<'EOF'
#!/usr/bin/env bash
printf '429'
EOF
cat >"$TMP/claude-codex-proxy" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$TMP/curl" "$TMP/claude-codex-proxy"
rm -f "$CAPTURE"

set +e
PATH="$TMP:$PATH" \
ALT_CLAUDE_BIN="$TMP/fake-alt-claude" \
ALT_CLAUDE_TEST_CAPTURE="$CAPTURE" \
ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" \
ALT_CLAUDE_CREDENTIALS_DIR="$CREDS" \
    "$BIN_DIR/alt-claude-nemotron" --yolo --resume session-456 >"$TMP/free-fail.out" 2>"$TMP/free-fail.err"
free_status=$?
set -e

[[ $free_status -eq 75 ]] || { echo "Falha: perfil free deveria retornar 75 quando indisponível" >&2; exit 1; }
[[ ! -e "$CAPTURE" ]] || { echo "Falha: perfil free tentou outro provider sem opt-in" >&2; exit 1; }
grep -q 'nenhum provider pago/por assinatura será usado automaticamente' "$TMP/free-fail.err"

# Fallback to Codex remains possible only with explicit opt-in.
PATH="$TMP:$PATH" \
ALT_CLAUDE_ALLOW_FALLBACK=1 \
ALT_CLAUDE_BIN="$TMP/fake-alt-claude" \
ALT_CLAUDE_TEST_CAPTURE="$CAPTURE" \
ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" \
ALT_CLAUDE_CREDENTIALS_DIR="$CREDS" \
    "$BIN_DIR/alt-claude-nemotron" --yolo --resume session-456 >/dev/null 2>&1

fallback_expected=$(cat <<'EOF'
--use
codex
--yolo
--resume
session-456
EOF
)
[[ "$(cat "$CAPTURE")" == "$fallback_expected" ]] || { echo "Falha no fallback Codex com opt-in" >&2; exit 1; }

# Explicit daily free quota exhaustion is cached: the second invocation must not hit OpenRouter again.
STATE_DIR="$TMP/state"
CURL_COUNT="$TMP/curl-count"
cat >"$TMP/curl" <<'EOF'
#!/usr/bin/env bash
count_file="${ALT_CLAUDE_TEST_CURL_COUNT:?}"
count=0
[[ -r "$count_file" ]] && count="$(cat "$count_file")"
printf '%s\n' "$((count + 1))" >"$count_file"

out=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o) out="$2"; shift 2 ;;
        -w) shift 2 ;;
        *) shift ;;
    esac
done
[[ -n "$out" ]] && printf '%s\n' '{"error":{"message":"Rate limit exceeded: free-models-per-day"}}' >"$out"
printf '429'
EOF
chmod +x "$TMP/curl"
rm -rf "$STATE_DIR"
rm -f "$CURL_COUNT"

for sid in session-quota-1 session-quota-2; do
    set +e
    PATH="$TMP:$PATH" \
    ALT_CLAUDE_BIN="$TMP/fake-alt-claude" \
    ALT_CLAUDE_TEST_CAPTURE="$CAPTURE" \
    ALT_CLAUDE_TEST_CURL_COUNT="$CURL_COUNT" \
    ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" \
    ALT_CLAUDE_CREDENTIALS_DIR="$CREDS" \
    ALT_CLAUDE_STATE_DIR="$STATE_DIR" \
        "$BIN_DIR/alt-claude-nemotron" --resume "$sid" >"$TMP/quota-$sid.out" 2>"$TMP/quota-$sid.err"
    quota_status=$?
    set -e
    [[ $quota_status -eq 75 ]] || { echo "Falha: quota free esgotada deveria retornar 75" >&2; exit 1; }
done

[[ "$(cat "$CURL_COUNT")" == "1" ]] || { echo "Falha: quota diária deveria evitar novo preflight após cache" >&2; exit 1; }
[[ "$(sed -n '1p' "$STATE_DIR/openrouter-free-exhausted")" == "$(date -u +%Y-%m-%d)" ]] || {
    echo "Falha: cache diário OpenRouter inválido" >&2
    exit 1
}
grep -q 'cota diária OpenRouter free esgotada' "$TMP/quota-session-quota-1.err"
grep -q 'cota diária OpenRouter free esgotada' "$TMP/quota-session-quota-2.err"

# Gateways known not to pass Claude Code server-side safeguards must force client-side classifier mode.
grep -q 'export CLAUDE_CODE_AUTO_MODE_SERVER=0' "$ROOT/alt-claude-core"
python3 - "$ROOT/alt-claude-core" <<'PY'
from pathlib import Path
s=Path(__import__('sys').argv[1]).read_text(encoding='utf-8')
for fn in ('start_copilot()', 'start_codex()', 'start_openrouter()', 'start_grok()'):
    pos=s.find(fn)
    if pos < 0:
        raise SystemExit(f'missing {fn}')
    block=s[pos:s.find('\n}', pos)+2]
    if 'export CLAUDE_CODE_AUTO_MODE_SERVER=0' not in block:
        raise SystemExit(f'{fn} does not force client-side auto classifier')
PY

# First block of direct free providers must be wired independently of OpenRouter.
for provider in groq cohere google nvidia kilo freeinference aihubmix; do
    grep -q "start_\${provider}()" "$ROOT/alt-claude-core" || { echo "Falha: provider ausente: $provider" >&2; exit 1; }
done
for profile in \
    groq-gpt-oss-120b \
    cohere-north-mini-code \
    google-gemini-3.8-flash \
    nvidia-deepseek-v4.1-flash \
    kilo-north-mini-code \
    freeinference-glm-5.3-flash \
    aihubmix-glm-5.3-flash
do
    [[ -r "$ROOT/profiles/$profile.env" ]] || { echo "Falha: perfil free direto ausente: $profile" >&2; exit 1; }
    grep -q '^FREE=1python3 - "$ROOT/tools/xai-anthropic-bridge.py" <<'PY'
import importlib.util, json, sys
path=sys.argv[1]
spec=importlib.util.spec_from_file_location("xai_bridge", path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
payload={
    "system":"You are a coding assistant.",
    "messages":[
        {"role":"user","content":[{"type":"text","text":"Read status"}]},
        {"role":"assistant","content":[{"type":"tool_use","id":"tool_1","name":"get_status","input":{"repo":"demo"}}]},
        {"role":"user","content":[{"type":"tool_result","tool_use_id":"tool_1","content":"clean"}]},
    ],
    "tools":[{"name":"get_status","description":"repo status","input_schema":{"type":"object","properties":{"repo":{"type":"string"}}}}],
    "tool_choice":{"type":"auto"},
}
msgs=mod._messages_to_openai(payload)
assert msgs[0] == {"role":"system","content":"You are a coding assistant."}
assert any(m.get("role")=="assistant" and m.get("tool_calls") for m in msgs)
assert any(m.get("role")=="tool" and m.get("tool_call_id")=="tool_1" for m in msgs)
tools=mod._tools_to_openai(payload)
assert tools[0]["function"]["name"]=="get_status"
assert mod._tool_choice_to_openai(payload["tool_choice"])=="auto"
PY

# Claude-compatible non-interactive JSON mode must fail fast and preserve errors as JSON.
printf 'KIMI_API_KEY=test-key\n' >"$CREDS/kimi.env"
cat >"$TMP/claude" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${CLAUDE_CODE_MAX_RETRIES:-unset}" >"${ALT_CLAUDE_TEST_RETRIES:?}"
printf '%s\n' '502 HTTP 403: {"code":"permission-denied","error":"blocked for test"}' >&2
exit 1
EOF
chmod +x "$TMP/claude"
set +e
json_error="$(
    PATH="$TMP:$PATH" \
    ALT_CLAUDE_CREDENTIALS_DIR="$CREDS" \
    ALT_CLAUDE_TEST_RETRIES="$TMP/retries" \
        "$BIN_DIR/alt-claude" --use kimi -p "ping" --output-format json 2>/dev/null
)"
json_status=$?
set -e
[[ $json_status -eq 1 ]] || { echo "Falha: JSON probe deveria preservar exit code 1" >&2; exit 1; }
[[ "$(cat "$TMP/retries")" == "0" ]] || { echo "Falha: JSON probe deveria desabilitar retries por padrão" >&2; exit 1; }
python3 - "$json_error" <<'PY'
import json, sys
obj=json.loads(sys.argv[1])
assert obj["type"] == "error"
assert obj["ok"] is False
assert obj["provider"] == "kimi"
assert obj["http_status"] in (403, 502)
assert obj["error_type"] == "permission-denied"
assert "blocked for test" in obj["message"]
PY

# Performance benchmark ranks enabled free profiles without touching paid/subscription routes.
PERF_PROFILES="$TMP/perf-profiles"
mkdir -p "$PERF_PROFILES"
cat >"$PERF_PROFILES/a.env" <<'EOF'
PROVIDER=openrouter
MODEL=test/a:free
DISPLAY_NAME="A"
STATUS=active
PRIVACY=review
CONTEXT_WINDOW=1000
SAFE_CONTEXT_TOKENS=800
AUTO_COMPACT_PCT=60
EOF
cat >"$PERF_PROFILES/b.env" <<'EOF'
PROVIDER=openrouter
MODEL=test/b:free
DISPLAY_NAME="B"
STATUS=active
PRIVACY=review
CONTEXT_WINDOW=1000
SAFE_CONTEXT_TOKENS=800
AUTO_COMPACT_PCT=60
EOF
cat >"$PERF_PROFILES/paid.env" <<'EOF'
PROVIDER=grok
MODEL=grok-4.7
DISPLAY_NAME="Paid"
STATUS=active
PRIVACY=review
CONTEXT_WINDOW=1000
SAFE_CONTEXT_TOKENS=800
AUTO_COMPACT_PCT=60
EOF
cat >"$TMP/fake-perf-alt-claude" <<'EOF'
#!/usr/bin/env bash
profile=""
prev=""
for arg in "$@"; do
  if [[ "$prev" == "--profile" ]]; then profile="$arg"; fi
  prev="$arg"
done
case "$profile" in
  a) result='{"arithmetic":139,"code":[4,16],"logic":12}' ;;
  b) result='{"arithmetic":139,"code":[4,16],"logic":11}' ;;
  paid) echo "paid profile must not run" >&2; exit 99 ;;
  *) exit 2 ;;
esac
python3 - "$result" <<'PY'
import json, sys
print(json.dumps({"type":"result","is_error":False,"result":sys.argv[1]}))
PY
EOF
chmod +x "$TMP/fake-perf-alt-claude"
perf_out="$(
  ALT_CLAUDE_BIN="$TMP/fake-perf-alt-claude" \
  ALT_CLAUDE_PROFILE_DIR="$PERF_PROFILES" \
  ALT_CLAUDE_STATE_DIR="$TMP/perf-state" \
  ALT_CLAUDE_CONFIG_DIR="$TMP/perf-config" \
    "$BIN_DIR/alt-claude" --list-performance --json
)"
python3 - "$perf_out" <<'PY'
import json, sys
rows=json.loads(sys.argv[1])
assert [r["profile"] for r in rows] == ["a","b"]
assert rows[0]["score"] == 3
assert rows[1]["score"] == 2
PY

# Model state: last-model is project-local, evaluations/disable state are shared globally.
MODEL_STATE_DIR="$TMP/model-state"
MODEL_CONFIG_DIR="$TMP/model-config"
PROJECT_A="$TMP/project-a"
PROJECT_B="$TMP/project-b"
mkdir -p "$PROJECT_A" "$PROJECT_B"
git -C "$PROJECT_A" init -q
git -C "$PROJECT_B" init -q

(
    cd "$PROJECT_A"
    ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
        python3 "$BIN_DIR/alt-claude-model-state" record-use \
        --profile north-mini-code --provider openrouter --model cohere/north-mini-code:free
    last="$(ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" "$BIN_DIR/alt-claude" --last-model)"
    [[ "$last" == *"cohere/north-mini-code:free via openrouter"* ]] || { echo "Falha: --last-model incorreto" >&2; exit 1; }
    ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
        "$BIN_DIR/alt-claude" --evaluate 5 >/dev/null
)
(
    cd "$PROJECT_B"
    set +e
    ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
        "$BIN_DIR/alt-claude" --last-model >/dev/null 2>"$TMP/project-b-last.err"
    st=$?
    set -e
    [[ $st -eq 2 ]] || { echo "Falha: --last-model deve ser isolado por Git root" >&2; exit 1; }
)
[[ -s "$MODEL_STATE_DIR/evaluations.jsonl" ]] || { echo "Falha: avaliação compartilhada não registrada" >&2; exit 1; }

ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
    "$BIN_DIR/alt-claude" --disable north-mini-code >/dev/null
set +e
ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
ALT_CLAUDE_BIN="$TMP/fake-alt-claude" ALT_CLAUDE_TEST_CAPTURE="$CAPTURE" \
ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" \
    "$BIN_DIR/alt-claude-north-mini-code" "ping" >/dev/null 2>"$TMP/disabled.err"
disabled_status=$?
set -e
[[ $disabled_status -eq 78 ]] || { echo "Falha: modelo disabled deveria bloquear uso" >&2; exit 1; }
grep -q 'ALERTA: modelo desabilitado' "$TMP/disabled.err"

ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
    "$BIN_DIR/alt-claude" --enable north-mini-code >/dev/null
ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
    python3 "$BIN_DIR/alt-claude-model-state" check-enabled cohere/north-mini-code:free

# Synthetic oversized session: North must refuse resume before hitting provider limit.
SESSION_ID="session-oversized"
SESSION_DIR="$TEST_HOME/.claude/projects/-tmp-project"
mkdir -p "$SESSION_DIR"
cat >"$SESSION_DIR/$SESSION_ID.jsonl" <<'EOF'
{"type":"user","sessionId":"session-oversized","cwd":"/tmp/project","gitBranch":"development","message":{"role":"user","content":"continue"}}
{"type":"assistant","sessionId":"session-oversized","cwd":"/tmp/project","gitBranch":"development","message":{"role":"assistant","content":[{"type":"text","text":"working"}],"usage":{"input_tokens":10000,"cache_read_input_tokens":190000,"cache_creation_input_tokens":0}}}
EOF

set +e
HOME="$TEST_HOME" \
ALT_CLAUDE_NO_FALLBACK=1 \
ALT_CLAUDE_BIN="$TMP/fake-alt-claude" \
ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" \
ALT_CLAUDE_COMPACTOR="$BIN_DIR/alt-claude-session-compact" \
    "$BIN_DIR/alt-claude-north-mini-code" --resume "$SESSION_ID" >/dev/null 2>"$TMP/guard.err"
guard_status=$?
set -e
[[ $guard_status -eq 75 ]] || { echo "Falha: context guard deveria retornar 75, retornou $guard_status" >&2; cat "$TMP/guard.err" >&2; exit 1; }
grep -q 'alt-claude compact' "$TMP/guard.err"

# Offline compactor generates a reusable handoff without any API/model call.
HOME="$TEST_HOME" python3 "$ROOT/tools/session-compact.py" "$SESSION_ID" -o "$TMP/handoff.md" >/dev/null
grep -q 'Claude Code session handoff' "$TMP/handoff.md"
grep -q '/tmp/project' "$TMP/handoff.md"
grep -q 'development' "$TMP/handoff.md"

# Every profile declares context AND privacy policy explicitly.
for profile in "$ROOT"/profiles/*.env; do
    (
        unset PROVIDER MODEL DISPLAY_NAME STATUS PRIVACY CONTEXT_WINDOW SAFE_CONTEXT_TOKENS AUTO_COMPACT_PCT
        # shellcheck disable=SC1090
        source "$profile"
        : "${PROVIDER:?PROVIDER ausente em $profile}"
        : "${MODEL:?MODEL ausente em $profile}"
        : "${DISPLAY_NAME:?DISPLAY_NAME ausente em $profile}"
        : "${STATUS:?STATUS ausente em $profile}"
        : "${PRIVACY:?PRIVACY ausente em $profile}"
        case "$PRIVACY" in sensitive_ok|review|public_only) ;; *) echo "PRIVACY inválido: $PRIVACY em $profile" >&2; exit 1 ;; esac
        : "${CONTEXT_WINDOW:?CONTEXT_WINDOW ausente em $profile}"
        : "${SAFE_CONTEXT_TOKENS:?SAFE_CONTEXT_TOKENS ausente em $profile}"
        : "${AUTO_COMPACT_PCT:?AUTO_COMPACT_PCT ausente em $profile}"
        (( SAFE_CONTEXT_TOKENS < CONTEXT_WINDOW ))
    )
done

for launcher in laguna nemotron north-mini-code grok laguna-xs nemotron-lightning nex-pro nex-mini inkling-small inkling deepseek-v4-flash glm-5.3-flash free; do
    [[ -x "$BIN_DIR/alt-claude-$launcher" ]] || { echo "Falha: launcher ausente: alt-claude-$launcher" >&2; exit 1; }
done

# Unified entry point groups privacy classes visibly.
profiles="$($BIN_DIR/alt-claude profiles)"
grep -q 'REVISAR PRIVACIDADE' <<<"$profiles"
grep -q 'NÃO USAR COM CÓDIGO SENSÍVEL' <<<"$profiles"
grep -q 'north-mini-code' <<<"$profiles"
grep -q 'inkling' <<<"$profiles"

# Policy engine uses a declarative project file and blocks REVIEW in sensitive mode.
POLICY_PROJECT="$TMP/policy-project"
mkdir -p "$POLICY_PROJECT"
git -C "$POLICY_PROJECT" init -q
(
  cd "$POLICY_PROJECT"
  "$BIN_DIR/alt-claude" policy init sensitive >/dev/null
  grep -q '^mode=sensitive$' .alt-claude/config
  grep -q '^deny_privacy=review,public_only$' .alt-claude/config
  set +e
  python3 "$BIN_DIR/alt-claude-policy" check --profile north-mini-code --provider openrouter --privacy review >/dev/null 2>"$TMP/policy.err"
  st=$?
  set -e
  [[ $st -eq 77 ]] || { echo "Falha: política sensível deveria bloquear REVIEW" >&2; exit 1; }
  grep -q 'BLOCKED by project policy' "$TMP/policy.err"
)

echo "OK: help, perfis, privacy policy, --yolo, --resume, context guard, offline compact e fallback"
 "$ROOT/profiles/$profile.env" || { echo "Falha: perfil não marcado FREE=1: $profile" >&2; exit 1; }
done

# Grok bridge translates Anthropic messages/tools into xAI/OpenAI-compatible structures without network access.
python3 - "$ROOT/tools/xai-anthropic-bridge.py" <<'PY'
import importlib.util, json, sys
path=sys.argv[1]
spec=importlib.util.spec_from_file_location("xai_bridge", path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
payload={
    "system":"You are a coding assistant.",
    "messages":[
        {"role":"user","content":[{"type":"text","text":"Read status"}]},
        {"role":"assistant","content":[{"type":"tool_use","id":"tool_1","name":"get_status","input":{"repo":"demo"}}]},
        {"role":"user","content":[{"type":"tool_result","tool_use_id":"tool_1","content":"clean"}]},
    ],
    "tools":[{"name":"get_status","description":"repo status","input_schema":{"type":"object","properties":{"repo":{"type":"string"}}}}],
    "tool_choice":{"type":"auto"},
}
msgs=mod._messages_to_openai(payload)
assert msgs[0] == {"role":"system","content":"You are a coding assistant."}
assert any(m.get("role")=="assistant" and m.get("tool_calls") for m in msgs)
assert any(m.get("role")=="tool" and m.get("tool_call_id")=="tool_1" for m in msgs)
tools=mod._tools_to_openai(payload)
assert tools[0]["function"]["name"]=="get_status"
assert mod._tool_choice_to_openai(payload["tool_choice"])=="auto"
PY

# Claude-compatible non-interactive JSON mode must fail fast and preserve errors as JSON.
printf 'KIMI_API_KEY=test-key\n' >"$CREDS/kimi.env"
cat >"$TMP/claude" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${CLAUDE_CODE_MAX_RETRIES:-unset}" >"${ALT_CLAUDE_TEST_RETRIES:?}"
printf '%s\n' '502 HTTP 403: {"code":"permission-denied","error":"blocked for test"}' >&2
exit 1
EOF
chmod +x "$TMP/claude"
set +e
json_error="$(
    PATH="$TMP:$PATH" \
    ALT_CLAUDE_CREDENTIALS_DIR="$CREDS" \
    ALT_CLAUDE_TEST_RETRIES="$TMP/retries" \
        "$BIN_DIR/alt-claude" --use kimi -p "ping" --output-format json 2>/dev/null
)"
json_status=$?
set -e
[[ $json_status -eq 1 ]] || { echo "Falha: JSON probe deveria preservar exit code 1" >&2; exit 1; }
[[ "$(cat "$TMP/retries")" == "0" ]] || { echo "Falha: JSON probe deveria desabilitar retries por padrão" >&2; exit 1; }
python3 - "$json_error" <<'PY'
import json, sys
obj=json.loads(sys.argv[1])
assert obj["type"] == "error"
assert obj["ok"] is False
assert obj["provider"] == "kimi"
assert obj["http_status"] in (403, 502)
assert obj["error_type"] == "permission-denied"
assert "blocked for test" in obj["message"]
PY

# Performance benchmark ranks enabled free profiles without touching paid/subscription routes.
PERF_PROFILES="$TMP/perf-profiles"
mkdir -p "$PERF_PROFILES"
cat >"$PERF_PROFILES/a.env" <<'EOF'
PROVIDER=openrouter
MODEL=test/a:free
DISPLAY_NAME="A"
STATUS=active
PRIVACY=review
CONTEXT_WINDOW=1000
SAFE_CONTEXT_TOKENS=800
AUTO_COMPACT_PCT=60
EOF
cat >"$PERF_PROFILES/b.env" <<'EOF'
PROVIDER=openrouter
MODEL=test/b:free
DISPLAY_NAME="B"
STATUS=active
PRIVACY=review
CONTEXT_WINDOW=1000
SAFE_CONTEXT_TOKENS=800
AUTO_COMPACT_PCT=60
EOF
cat >"$PERF_PROFILES/paid.env" <<'EOF'
PROVIDER=grok
MODEL=grok-4.7
DISPLAY_NAME="Paid"
STATUS=active
PRIVACY=review
CONTEXT_WINDOW=1000
SAFE_CONTEXT_TOKENS=800
AUTO_COMPACT_PCT=60
EOF
cat >"$TMP/fake-perf-alt-claude" <<'EOF'
#!/usr/bin/env bash
profile=""
prev=""
for arg in "$@"; do
  if [[ "$prev" == "--profile" ]]; then profile="$arg"; fi
  prev="$arg"
done
case "$profile" in
  a) result='{"arithmetic":139,"code":[4,16],"logic":12}' ;;
  b) result='{"arithmetic":139,"code":[4,16],"logic":11}' ;;
  paid) echo "paid profile must not run" >&2; exit 99 ;;
  *) exit 2 ;;
esac
python3 - "$result" <<'PY'
import json, sys
print(json.dumps({"type":"result","is_error":False,"result":sys.argv[1]}))
PY
EOF
chmod +x "$TMP/fake-perf-alt-claude"
perf_out="$(
  ALT_CLAUDE_BIN="$TMP/fake-perf-alt-claude" \
  ALT_CLAUDE_PROFILE_DIR="$PERF_PROFILES" \
  ALT_CLAUDE_STATE_DIR="$TMP/perf-state" \
  ALT_CLAUDE_CONFIG_DIR="$TMP/perf-config" \
    "$BIN_DIR/alt-claude" --list-performance --json
)"
python3 - "$perf_out" <<'PY'
import json, sys
rows=json.loads(sys.argv[1])
assert [r["profile"] for r in rows] == ["a","b"]
assert rows[0]["score"] == 3
assert rows[1]["score"] == 2
PY

# Model state: last-model is project-local, evaluations/disable state are shared globally.
MODEL_STATE_DIR="$TMP/model-state"
MODEL_CONFIG_DIR="$TMP/model-config"
PROJECT_A="$TMP/project-a"
PROJECT_B="$TMP/project-b"
mkdir -p "$PROJECT_A" "$PROJECT_B"
git -C "$PROJECT_A" init -q
git -C "$PROJECT_B" init -q

(
    cd "$PROJECT_A"
    ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
        python3 "$BIN_DIR/alt-claude-model-state" record-use \
        --profile north-mini-code --provider openrouter --model cohere/north-mini-code:free
    last="$(ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" "$BIN_DIR/alt-claude" --last-model)"
    [[ "$last" == *"cohere/north-mini-code:free via openrouter"* ]] || { echo "Falha: --last-model incorreto" >&2; exit 1; }
    ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
        "$BIN_DIR/alt-claude" --evaluate 5 >/dev/null
)
(
    cd "$PROJECT_B"
    set +e
    ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
        "$BIN_DIR/alt-claude" --last-model >/dev/null 2>"$TMP/project-b-last.err"
    st=$?
    set -e
    [[ $st -eq 2 ]] || { echo "Falha: --last-model deve ser isolado por Git root" >&2; exit 1; }
)
[[ -s "$MODEL_STATE_DIR/evaluations.jsonl" ]] || { echo "Falha: avaliação compartilhada não registrada" >&2; exit 1; }

ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
    "$BIN_DIR/alt-claude" --disable north-mini-code >/dev/null
set +e
ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
ALT_CLAUDE_BIN="$TMP/fake-alt-claude" ALT_CLAUDE_TEST_CAPTURE="$CAPTURE" \
ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" \
    "$BIN_DIR/alt-claude-north-mini-code" "ping" >/dev/null 2>"$TMP/disabled.err"
disabled_status=$?
set -e
[[ $disabled_status -eq 78 ]] || { echo "Falha: modelo disabled deveria bloquear uso" >&2; exit 1; }
grep -q 'ALERTA: modelo desabilitado' "$TMP/disabled.err"

ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
    "$BIN_DIR/alt-claude" --enable north-mini-code >/dev/null
ALT_CLAUDE_STATE_DIR="$MODEL_STATE_DIR" ALT_CLAUDE_CONFIG_DIR="$MODEL_CONFIG_DIR" \
    python3 "$BIN_DIR/alt-claude-model-state" check-enabled cohere/north-mini-code:free

# Synthetic oversized session: North must refuse resume before hitting provider limit.
SESSION_ID="session-oversized"
SESSION_DIR="$TEST_HOME/.claude/projects/-tmp-project"
mkdir -p "$SESSION_DIR"
cat >"$SESSION_DIR/$SESSION_ID.jsonl" <<'EOF'
{"type":"user","sessionId":"session-oversized","cwd":"/tmp/project","gitBranch":"development","message":{"role":"user","content":"continue"}}
{"type":"assistant","sessionId":"session-oversized","cwd":"/tmp/project","gitBranch":"development","message":{"role":"assistant","content":[{"type":"text","text":"working"}],"usage":{"input_tokens":10000,"cache_read_input_tokens":190000,"cache_creation_input_tokens":0}}}
EOF

set +e
HOME="$TEST_HOME" \
ALT_CLAUDE_NO_FALLBACK=1 \
ALT_CLAUDE_BIN="$TMP/fake-alt-claude" \
ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" \
ALT_CLAUDE_COMPACTOR="$BIN_DIR/alt-claude-session-compact" \
    "$BIN_DIR/alt-claude-north-mini-code" --resume "$SESSION_ID" >/dev/null 2>"$TMP/guard.err"
guard_status=$?
set -e
[[ $guard_status -eq 75 ]] || { echo "Falha: context guard deveria retornar 75, retornou $guard_status" >&2; cat "$TMP/guard.err" >&2; exit 1; }
grep -q 'alt-claude compact' "$TMP/guard.err"

# Offline compactor generates a reusable handoff without any API/model call.
HOME="$TEST_HOME" python3 "$ROOT/tools/session-compact.py" "$SESSION_ID" -o "$TMP/handoff.md" >/dev/null
grep -q 'Claude Code session handoff' "$TMP/handoff.md"
grep -q '/tmp/project' "$TMP/handoff.md"
grep -q 'development' "$TMP/handoff.md"

# Every profile declares context AND privacy policy explicitly.
for profile in "$ROOT"/profiles/*.env; do
    (
        unset PROVIDER MODEL DISPLAY_NAME STATUS PRIVACY CONTEXT_WINDOW SAFE_CONTEXT_TOKENS AUTO_COMPACT_PCT
        # shellcheck disable=SC1090
        source "$profile"
        : "${PROVIDER:?PROVIDER ausente em $profile}"
        : "${MODEL:?MODEL ausente em $profile}"
        : "${DISPLAY_NAME:?DISPLAY_NAME ausente em $profile}"
        : "${STATUS:?STATUS ausente em $profile}"
        : "${PRIVACY:?PRIVACY ausente em $profile}"
        case "$PRIVACY" in sensitive_ok|review|public_only) ;; *) echo "PRIVACY inválido: $PRIVACY em $profile" >&2; exit 1 ;; esac
        : "${CONTEXT_WINDOW:?CONTEXT_WINDOW ausente em $profile}"
        : "${SAFE_CONTEXT_TOKENS:?SAFE_CONTEXT_TOKENS ausente em $profile}"
        : "${AUTO_COMPACT_PCT:?AUTO_COMPACT_PCT ausente em $profile}"
        (( SAFE_CONTEXT_TOKENS < CONTEXT_WINDOW ))
    )
done

for launcher in laguna nemotron north-mini-code grok laguna-xs nemotron-lightning nex-pro nex-mini inkling-small inkling deepseek-v4-flash glm-5.3-flash free; do
    [[ -x "$BIN_DIR/alt-claude-$launcher" ]] || { echo "Falha: launcher ausente: alt-claude-$launcher" >&2; exit 1; }
done

# Unified entry point groups privacy classes visibly.
profiles="$($BIN_DIR/alt-claude profiles)"
grep -q 'REVISAR PRIVACIDADE' <<<"$profiles"
grep -q 'NÃO USAR COM CÓDIGO SENSÍVEL' <<<"$profiles"
grep -q 'north-mini-code' <<<"$profiles"
grep -q 'inkling' <<<"$profiles"

# Policy engine uses a declarative project file and blocks REVIEW in sensitive mode.
POLICY_PROJECT="$TMP/policy-project"
mkdir -p "$POLICY_PROJECT"
git -C "$POLICY_PROJECT" init -q
(
  cd "$POLICY_PROJECT"
  "$BIN_DIR/alt-claude" policy init sensitive >/dev/null
  grep -q '^mode=sensitive$' .alt-claude/config
  grep -q '^deny_privacy=review,public_only$' .alt-claude/config
  set +e
  python3 "$BIN_DIR/alt-claude-policy" check --profile north-mini-code --provider openrouter --privacy review >/dev/null 2>"$TMP/policy.err"
  st=$?
  set -e
  [[ $st -eq 77 ]] || { echo "Falha: política sensível deveria bloquear REVIEW" >&2; exit 1; }
  grep -q 'BLOCKED by project policy' "$TMP/policy.err"
)

echo "OK: help, perfis, privacy policy, --yolo, --resume, context guard, offline compact e fallback"
