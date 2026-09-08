#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${ALT_CLAUDE_INSTALL_DIR:-$HOME/.local/bin}"
TARGET="$TARGET_DIR/alt-claude"

mkdir -p "$TARGET_DIR"
install -m 0755 "$ROOT/alt-claude" "$TARGET"

echo "Instalado: $TARGET"
case ":$PATH:" in
  *":$TARGET_DIR:"*) ;;
  *) echo "Aviso: $TARGET_DIR não está no PATH." ;;
esac
