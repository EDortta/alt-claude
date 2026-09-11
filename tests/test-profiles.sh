#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

BIN_DIR="$TMP/bin"
DATA_DIR="$TMP/data"
CAPTURE="$TMP/args.txt"
mkdir -p "$BIN_DIR" "$DATA_DIR"

cat >"$TMP/fake-alt-claude" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"${ALT_CLAUDE_TEST_CAPTURE:?}"
EOF
chmod +x "$TMP/fake-alt-claude"

ALT_CLAUDE_INSTALL_DIR="$BIN_DIR" \
ALT_CLAUDE_DATA_DIR="$DATA_DIR" \
    bash "$ROOT/install.sh" >/dev/null

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

if [[ "$actual" != "$expected" ]]; then
    echo "Falha: forwarding de argumentos diferente do esperado." >&2
    diff -u <(printf '%s\n' "$expected") <(printf '%s\n' "$actual") || true
    exit 1
fi

for profile in "$ROOT"/profiles/*.env; do
    (
        # shellcheck disable=SC1090
        source "$profile"
        : "${PROVIDER:?PROVIDER ausente em $profile}"
        : "${MODEL:?MODEL ausente em $profile}"
        : "${DISPLAY_NAME:?DISPLAY_NAME ausente em $profile}"
        : "${STATUS:?STATUS ausente em $profile}"
    )
done

for launcher in laguna nemotron north-mini-code laguna-xs nemotron-lightning nex-pro nex-mini inkling-small free; do
    [[ -x "$BIN_DIR/alt-claude-$launcher" ]] || {
        echo "Falha: launcher não instalado: alt-claude-$launcher" >&2
        exit 1
    }
done

echo "OK: perfis, instalação, --yolo e --resume"
