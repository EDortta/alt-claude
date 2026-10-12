#!/usr/bin/env python3
"""Benchmark enabled free alt-claude profiles with one compact deterministic probe."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

STATE_ROOT = pathlib.Path(
    os.environ.get(
        "ALT_CLAUDE_STATE_DIR",
        os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "alt-claude"),
    )
)
CONFIG_ROOT = pathlib.Path(
    os.environ.get(
        "ALT_CLAUDE_CONFIG_DIR",
        os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "alt-claude"),
    )
)
PROFILE_DIR = pathlib.Path(
    os.environ.get(
        "ALT_CLAUDE_PROFILE_DIR",
        os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "alt-claude", "profiles"),
    )
)

PROMPT = (
    'Responda SOMENTE com JSON válido, sem markdown. Resolva três microtestes: '
    '1) arithmetic = 37*4-9; '
    '2) code = resultado de [x*x for x in [1,2,3,4] if x%2==0]; '
    '3) logic = menor inteiro maior que 10 divisível por 3 e por 4. '
    'Formato exato: {"arithmetic":N,"code":[...],"logic":N}'
)
EXPECTED = {"arithmetic": 139, "code": [4, 16], "logic": 12}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_env_file(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        try:
            parsed = shlex.split(val, posix=True)
            out[key] = parsed[0] if parsed else ""
        except ValueError:
            out[key] = val.strip('"').strip("'")
    return out


def load_disabled() -> set[str]:
    path = CONFIG_ROOT / "disabled-models.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        models = obj.get("models", {})
        return set(models) if isinstance(models, dict) else set()
    except Exception:
        return set()


def is_free_profile(meta: dict[str, str]) -> bool:
    model = meta.get("MODEL", "")
    provider = meta.get("PROVIDER", "")
    return provider == "openrouter" and (model.endswith(":free") or model == "openrouter/free")


def extract_model_answer(stdout: str) -> tuple[dict[str, Any] | None, str]:
    text = stdout.strip()
    try:
        outer = json.loads(text)
    except Exception:
        return None, "invalid-wrapper-json"
    if not isinstance(outer, dict):
        return None, "unexpected-wrapper"
    if outer.get("is_error") or outer.get("type") == "error" or outer.get("terminal_reason") == "api_error":
        return None, str(outer.get("result") or outer.get("message") or "api-error")

    result = outer.get("result")
    if isinstance(result, dict):
        answer = result
    elif isinstance(result, str):
        candidate = result.strip()
        fence = chr(96) * 3
        if candidate.startswith(fence):
            candidate = candidate.strip(chr(96)).strip()
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
        try:
            answer = json.loads(candidate)
        except Exception:
            return None, "invalid-result-json"
    else:
        return None, "missing-result"
    return answer if isinstance(answer, dict) else None, "ok"


def score_answer(answer: dict[str, Any] | None) -> int:
    if answer is None:
        return 0
    return sum(1 for key, expected in EXPECTED.items() if answer.get(key) == expected)


def append_result(obj: dict[str, Any]) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    path = STATE_ROOT / "performance.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def run_profile(alt_claude: str, name: str, meta: dict[str, str], timeout: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["ALT_CLAUDE_NO_FALLBACK"] = "1"
    env["ALT_CLAUDE_NO_RECORD_USE"] = "1"
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [alt_claude, "--profile", name, "-p", PROMPT, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        elapsed = time.monotonic() - started
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        return {
            "timestamp": now_iso(), "profile": name, "model": meta.get("MODEL"),
            "provider": meta.get("PROVIDER"), "ok": False, "score": 0,
            "tests": 3, "seconds": round(elapsed, 3), "status": "timeout",
        }

    answer, status = extract_model_answer(proc.stdout)
    score = score_answer(answer)
    ok = proc.returncode == 0 and score == 3
    if proc.returncode != 0 and status == "ok":
        status = f"exit-{proc.returncode}"
    elif score < 3 and status == "ok":
        status = f"partial-{score}/3"
    result = {
        "timestamp": now_iso(),
        "profile": name,
        "model": meta.get("MODEL"),
        "provider": meta.get("PROVIDER"),
        "ok": ok,
        "score": score,
        "tests": 3,
        "seconds": round(elapsed, 3),
        "status": status,
    }
    if not ok:
        err = (proc.stderr or "").strip()
        if err:
            result["detail"] = err[-1200:]
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Benchmark de performance dos perfis gratuitos habilitados")
    p.add_argument("--json", action="store_true")
    p.add_argument("--timeout", type=int, default=45)
    p.add_argument("--all", action="store_true", help="inclui perfis não-free (pode consumir quota paga)")
    args = p.parse_args()

    alt_claude = os.environ.get("ALT_CLAUDE_BIN", "alt-claude")
    if not PROFILE_DIR.is_dir():
        print(f"Erro: diretório de perfis não encontrado: {PROFILE_DIR}", file=sys.stderr)
        return 2

    disabled = load_disabled()
    candidates: list[tuple[str, dict[str, str]]] = []
    for path in sorted(PROFILE_DIR.glob("*.env")):
        meta = parse_env_file(path)
        model = meta.get("MODEL", "")
        if not model or model in disabled:
            continue
        if not args.all and not is_free_profile(meta):
            continue
        candidates.append((path.stem, meta))

    if not candidates:
        print("Nenhum perfil elegível para benchmark.", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    for name, meta in candidates:
        if not args.json:
            print(f"Testando {name} ...", file=sys.stderr, flush=True)
        result = run_profile(alt_claude, name, meta, args.timeout)
        append_result(result)
        results.append(result)

    ranked = sorted(results, key=lambda r: (-int(r["score"]), float(r["seconds"]), str(r["profile"])))

    if args.json:
        print(json.dumps(ranked, ensure_ascii=False))
        return 0

    print()
    print(f"{'#':>2}  {'PROFILE':24} {'SCORE':7} {'TEMPO':9} STATUS")
    print(f"{'--':>2}  {'-'*24} {'-'*7} {'-'*9} {'-'*24}")
    for idx, r in enumerate(ranked, 1):
        print(f"{idx:>2}  {str(r['profile']):24.24} {r['score']}/3    {r['seconds']:>7.2f}s {r['status']}")
    print()
    print("Ranking: maior acerto primeiro; em empate, menor tempo total.")
    print(f"Histórico: {STATE_ROOT / 'performance.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
