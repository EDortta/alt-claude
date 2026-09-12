#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="$(mktemp)"
trap 'rm -f "$CACHE"' EXIT

command -v curl >/dev/null 2>&1 || { echo "Erro: curl não encontrado." >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "Erro: python3 não encontrado." >&2; exit 2; }

curl -fsS --connect-timeout 8 --max-time 30 https://openrouter.ai/api/v1/models >"$CACHE"

printf '%-24s %-10s %-7s %-10s %-10s %-10s %s\n' "PERFIL" "STATUS" "FREE" "API_CTX" "DECL_CTX" "SAFE" "MODELO"
printf '%-24s %-10s %-7s %-10s %-10s %-10s %s\n' "------------------------" "----------" "-------" "----------" "----------" "----------" "----------------------------------------"

failed=0
for file in "$ROOT"/profiles/*.env; do
    unset PROVIDER MODEL DISPLAY_NAME STATUS NOTES CONTEXT_WINDOW SAFE_CONTEXT_TOKENS AUTO_COMPACT_PCT
    # shellcheck disable=SC1090
    source "$file"
    profile="$(basename "$file" .env)"

    if [[ "$PROVIDER" != "openrouter" ]]; then
        printf '%-24s %-10s %-7s %-10s %-10s %-10s %s\n' "$profile" "SKIP" "N/D" "N/D" "${CONTEXT_WINDOW:-N/D}" "${SAFE_CONTEXT_TOKENS:-N/D}" "$MODEL"
        continue
    fi

    result="$(python3 - "$CACHE" "$MODEL" <<'PY'
import json, sys
path, wanted = sys.argv[1], sys.argv[2]
with open(path, encoding='utf-8') as f:
    payload = json.load(f)
models = payload.get('data', payload if isinstance(payload, list) else [])
for model in models:
    if model.get('id') == wanted:
        pricing = model.get('pricing') or {}
        prompt = str(pricing.get('prompt', ''))
        completion = str(pricing.get('completion', ''))
        free = prompt in {'0','0.0','0.000000'} and completion in {'0','0.0','0.000000'}
        ctx = model.get('context_length') or 0
        print(f"FOUND\t{'YES' if free else 'NO'}\t{ctx}")
        raise SystemExit(0)
print('MISSING\tNO\t0')
PY
)"

    IFS=$'\t' read -r state free api_ctx <<< "$result"
    decl="${CONTEXT_WINDOW:-0}"
    safe="${SAFE_CONTEXT_TOKENS:-0}"

    if [[ "$state" != "FOUND" ]]; then
        printf '%-24s %-10s %-7s %-10s %-10s %-10s %s\n' "$profile" "MISSING" "-" "-" "$decl" "$safe" "$MODEL"
        failed=1
        continue
    fi

    status="OK"
    [[ "$free" == "YES" ]] || status="PAID"
    if [[ "$MODEL" == *":free" || "$MODEL" == "openrouter/free" ]]; then
        [[ "$free" == "YES" ]] || failed=1
    fi
    if [[ "$api_ctx" =~ ^[0-9]+$ && "$api_ctx" -gt 0 && "$safe" =~ ^[0-9]+$ && "$safe" -ge "$api_ctx" ]]; then
        status="BAD_CTX"
        failed=1
    fi
    if [[ "$decl" =~ ^[0-9]+$ && "$decl" -gt 0 && "$api_ctx" =~ ^[0-9]+$ && "$api_ctx" -gt 0 && "$decl" -gt "$api_ctx" ]]; then
        status="CTX_DRIFT"
        failed=1
    fi

    printf '%-24s %-10s %-7s %-10s %-10s %-10s %s\n' "$profile" "$status" "$free" "$api_ctx" "$decl" "$safe" "$MODEL"
done

exit "$failed"
