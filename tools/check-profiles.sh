#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="$(mktemp)"
trap 'rm -f "$CACHE"' EXIT

command -v curl >/dev/null 2>&1 || { echo "Erro: curl não encontrado." >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "Erro: python3 não encontrado." >&2; exit 2; }

curl -fsS --connect-timeout 8 --max-time 30 \
    https://openrouter.ai/api/v1/models >"$CACHE"

printf '%-24s %-11s %-8s %s\n' "PERFIL" "STATUS" "GRÁTIS" "MODELO"
printf '%-24s %-11s %-8s %s\n' "------------------------" "-----------" "--------" "-----------------------------------------------"

failed=0
for file in "$ROOT"/profiles/*.env; do
    unset PROVIDER MODEL DISPLAY_NAME STATUS NOTES
    # shellcheck disable=SC1090
    source "$file"
    profile="$(basename "$file" .env)"

    if [[ "$PROVIDER" != "openrouter" ]]; then
        printf '%-24s %-11s %-8s %s\n' "$profile" "SKIP" "N/D" "$MODEL"
        continue
    fi

    result="$(python3 - "$CACHE" "$MODEL" <<'PY'
import json, sys
path, wanted = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    payload = json.load(f)
models = payload.get("data", payload if isinstance(payload, list) else [])
for model in models:
    if model.get("id") == wanted:
        pricing = model.get("pricing") or {}
        prompt = str(pricing.get("prompt", ""))
        completion = str(pricing.get("completion", ""))
        free = prompt in {"0", "0.0", "0.000000"} and completion in {"0", "0.0", "0.000000"}
        print("FOUND\t" + ("YES" if free else "NO"))
        raise SystemExit(0)
print("MISSING\tNO")
PY
)"

    state="${result%%$'\t'*}"
    free="${result#*$'\t'}"

    if [[ "$state" == "FOUND" ]]; then
        printf '%-24s %-11s %-8s %s\n' "$profile" "OK" "$free" "$MODEL"
        [[ "$free" == "YES" ]] || failed=1
    else
        printf '%-24s %-11s %-8s %s\n' "$profile" "MISSING" "-" "$MODEL"
        failed=1
    fi
done

exit "$failed"
