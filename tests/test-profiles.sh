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

python3 -m py_compile "$ROOT/tools/session-compact.py"

cat >"$TMP/fake-alt-claude" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"${ALT_CLAUDE_TEST_CAPTURE:?}"
EOF
chmod +x "$TMP/fake-alt-claude"

ALT_CLAUDE_INSTALL_DIR="$BIN_DIR" ALT_CLAUDE_DATA_DIR="$DATA_DIR" bash "$ROOT/install.sh" >/dev/null

# Normal forwarding: no real session exists, so resume guard stays non-blocking.
ALT_CLAUDE_NO_FALLBACK=1 \
ALT_CLAUDE_BIN="$TMP/fake-alt-claude" \
ALT_CLAUDE_TEST_CAPTURE="$CAPTURE" \
ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" \
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

# OpenRouter exhausted -> Codex fallback, preserving common flags.
printf 'OPENROUTER_API_KEY=test-key\n' >"$CREDS/openrouter.env"
cat >"$TMP/curl" <<'EOF'
#!/usr/bin/env bash
printf '429'
EOF
cat >"$TMP/claude-codex-proxy" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$TMP/curl" "$TMP/claude-codex-proxy"

PATH="$TMP:$PATH" \
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
[[ "$(cat "$CAPTURE")" == "$fallback_expected" ]] || { echo "Falha no fallback Codex" >&2; exit 1; }

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

# Every profile declares a context policy.
for profile in "$ROOT"/profiles/*.env; do
    (
        unset PROVIDER MODEL DISPLAY_NAME STATUS CONTEXT_WINDOW SAFE_CONTEXT_TOKENS AUTO_COMPACT_PCT
        # shellcheck disable=SC1090
        source "$profile"
        : "${PROVIDER:?PROVIDER ausente em $profile}"
        : "${MODEL:?MODEL ausente em $profile}"
        : "${DISPLAY_NAME:?DISPLAY_NAME ausente em $profile}"
        : "${STATUS:?STATUS ausente em $profile}"
        : "${CONTEXT_WINDOW:?CONTEXT_WINDOW ausente em $profile}"
        : "${SAFE_CONTEXT_TOKENS:?SAFE_CONTEXT_TOKENS ausente em $profile}"
        : "${AUTO_COMPACT_PCT:?AUTO_COMPACT_PCT ausente em $profile}"
        (( SAFE_CONTEXT_TOKENS < CONTEXT_WINDOW ))
    )
done

for launcher in laguna nemotron north-mini-code laguna-xs nemotron-lightning nex-pro nex-mini inkling-small inkling deepseek-v4-flash glm-5.3-flash free; do
    [[ -x "$BIN_DIR/alt-claude-$launcher" ]] || { echo "Falha: launcher ausente: alt-claude-$launcher" >&2; exit 1; }
done

# Unified entry point exists and lists profiles.
ALT_CLAUDE_PROFILE_DIR="$DATA_DIR/profiles" "$BIN_DIR/alt-claude" profiles | grep -q 'north-mini-code'

echo "OK: unified launcher, perfis, --yolo, --resume, context guard, offline compact e fallback"
