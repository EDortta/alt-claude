#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${ALT_CLAUDE_INSTALL_DIR:-$HOME/.local/bin}"

if [[ -z "$TARGET_DIR" ]]; then
    printf '%s\n' 'Erro: ALT_CLAUDE_INSTALL_DIR não pode ser vazio.' >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"

installed=0
for source in "$ROOT"/alt-claude*; do
    [[ -f "$source" ]] || continue

    name="$(basename "$source")"
    install -m 0755 "$source" "$TARGET_DIR/$name"
    printf 'Instalado: %s\n' "$TARGET_DIR/$name"
    installed=$((installed + 1))
done

if (( installed == 0 )); then
    printf 'Erro: nenhum launcher alt-claude* encontrado em %s.\n' "$ROOT" >&2
    exit 1
fi

case ":${PATH:-}:" in
    *":$TARGET_DIR:"*) ;;
    *) printf 'Aviso: %s não está no PATH.\n' "$TARGET_DIR" >&2 ;;
esac
