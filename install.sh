#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${ALT_CLAUDE_INSTALL_DIR:-$HOME/.local/bin}"
DATA_DIR="${ALT_CLAUDE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/alt-claude}"
PROFILE_DIR="$DATA_DIR/profiles"

if [[ -z "$TARGET_DIR" ]]; then
    printf '%s\n' 'Erro: ALT_CLAUDE_INSTALL_DIR não pode ser vazio.' >&2
    exit 1
fi

mkdir -p "$TARGET_DIR" "$PROFILE_DIR"

install -m 0755 "$ROOT/alt-claude" "$TARGET_DIR/alt-claude"
install -m 0755 "$ROOT/alt-claude-core" "$TARGET_DIR/alt-claude-core"
install -m 0755 "$ROOT/alt-claude-profile" "$TARGET_DIR/alt-claude-profile"
install -m 0755 "$ROOT/tools/session-compact.py" "$TARGET_DIR/alt-claude-session-compact"

printf 'Instalado: %s\n' "$TARGET_DIR/alt-claude"
printf 'Instalado: %s\n' "$TARGET_DIR/alt-claude-core"
printf 'Instalado: %s\n' "$TARGET_DIR/alt-claude-profile"
printf 'Instalado: %s\n' "$TARGET_DIR/alt-claude-session-compact"

shopt -s nullglob
profiles=("$ROOT"/profiles/*.env)

if (( ${#profiles[@]} == 0 )); then
    printf 'Erro: nenhum perfil encontrado em %s/profiles.\n' "$ROOT" >&2
    exit 1
fi

for source in "${profiles[@]}"; do
    name="$(basename "$source" .env)"
    install -m 0644 "$source" "$PROFILE_DIR/$name.env"

    launcher="$TARGET_DIR/alt-claude-$name"
    cat >"$launcher" <<EOF
#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
exec "\$SELF_DIR/alt-claude" --profile "$name" "\$@"
EOF
    chmod 0755 "$launcher"
    printf 'Instalado: %s -> perfil %s\n' "$launcher" "$name"
done

case ":${PATH:-}:" in
    *":$TARGET_DIR:"*) ;;
    *) printf 'Aviso: %s não está no PATH.\n' "$TARGET_DIR" >&2 ;;
esac

printf '\nPerfis instalados em: %s\n' "$PROFILE_DIR"
printf 'Uso principal: alt-claude --profile <perfil> [--yolo] [--resume SESSION_ID]\n'
printf 'Compatibilidade: alt-claude-<perfil> continua funcionando.\n'
printf 'Recuperação offline: alt-claude compact SESSION_ID\n'
