#!/usr/bin/env python3
"""Evidence-rich probes for every free alt-claude profile.

Only free profiles are tested. Fallback is disabled. Project privacy policy is
ignored only for this diagnostic run so public_only routes can actually be
probed. The run does not update project-local last-model state.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import time
from typing import Any

PROMPT = (
    'Responda SOMENTE com JSON valido, sem markdown. '
    'Resolva: arithmetic=37*4-9; '
    'code=resultado de [x*x for x in [1,2,3,4] if x%2==0]; '
    'logic=menor inteiro maior que 10 divisivel por 3 e por 4. '
    'Formato exato: {"arithmetic":N,"code":[...],"logic":N}'
)
EXPECTED = {"arithmetic": 139, "code": [4, 16], "logic": 12}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_capture(cmd: list[str], cwd: pathlib.Path, timeout: int = 15) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
        return {
            "returncode": proc.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as exc:
        return {
            "returncode": None,
            "seconds": round(time.monotonic() - started, 3),
            "stdout": "",
            "stderr": repr(exc),
        }


def parse_env(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            parts = shlex.split(value.strip(), posix=True)
            out[key.strip()] = parts[0] if parts else ""
        except ValueError:
            out[key.strip()] = value.strip().strip("'\"")
    return out


def is_free(meta: dict[str, str]) -> bool:
    flag = meta.get("FREE", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    model = meta.get("MODEL", "")
    provider = meta.get("PROVIDER", "")
    return provider == "openrouter" and (model.endswith(":free") or model == "openrouter/free")


def classify(returncode: int | None, stdout: str, stderr: str) -> str:
    low = ("\n".join(x for x in (stderr.strip(), stdout.strip()) if x)).lower()
    if returncode is None:
        return "runner-error"
    if "blocked by project policy" in low or ("privacy class" in low and "is denied" in low):
        return "project-policy-blocked"
    if "modelo desabilitado" in low:
        return "model-disabled"
    if "bridge openai-compatible nao encontrado" in low or "bridge openai-compatible não encontrado" in low:
        return "bridge-missing"
    if "credencial nao encontrada" in low or "credencial não encontrada" in low or "api_key nao definida" in low or "api_key não definida" in low:
        return "credential-missing"
    if "free-models-per-day" in low or "cota diaria openrouter free esgotada" in low or "cota diária openrouter free esgotada" in low:
        return "provider-quota-exhausted"
    if "modelo gratuito indisponivel" in low or "modelo gratuito indisponível" in low or "indisponivel no preflight" in low or "indisponível no preflight" in low:
        return "provider-unavailable"
    if "rate limit" in low or "resource_exhausted" in low or "429" in low:
        return "rate-limited"
    if "permission-denied" in low or "permission denied" in low or "403" in low:
        return "permission-denied"
    if "timeout" in low or returncode == 124:
        return "timeout"
    if returncode != 0:
        return f"launch-error-{returncode}"
    return "response"


def parse_answer(stdout: str) -> tuple[dict[str, Any] | None, str | None]:
    text = stdout.strip()
    if not text:
        return None, None
    try:
        wrapper = json.loads(text)
    except Exception:
        return None, None
    if not isinstance(wrapper, dict):
        return None, None
    if wrapper.get("type") == "error" or wrapper.get("is_error") is True or wrapper.get("terminal_reason") == "api_error":
        return None, str(wrapper.get("message") or wrapper.get("result") or "api-error")
    result = wrapper.get("result")
    if isinstance(result, dict):
        return result, None
    if not isinstance(result, str):
        return None, None
    candidate = result.strip()
    if candidate.startswith("~~~"):
        candidate = candidate.strip("~").strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].strip()
    try:
        answer = json.loads(candidate)
    except Exception:
        return None, None
    return answer if isinstance(answer, dict) else None, None


def score(answer: dict[str, Any] | None) -> int | None:
    if answer is None:
        return None
    return sum(1 for key, expected in EXPECTED.items() if answer.get(key) == expected)


def path_info(command: str) -> dict[str, Any]:
    found = shutil.which(command)
    info: dict[str, Any] = {"command": command, "path": found}
    if found:
        path = pathlib.Path(found)
        info["executable"] = os.access(path, os.X_OK)
        info["realpath"] = str(path.resolve())
        try:
            info["mode"] = oct(path.stat().st_mode & 0o777)
        except OSError:
            pass
    return info


def write_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_dir", help="pasta que recebera as evidencias")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--profile-dir", default="")
    parser.add_argument("--alt-claude", default="")
    args = parser.parse_args()

    root = pathlib.Path(__file__).resolve().parents[1]
    profile_dir = pathlib.Path(args.profile_dir).expanduser().resolve() if args.profile_dir else root / "profiles"
    alt_claude = args.alt_claude or shutil.which("alt-claude") or str(root / "alt-claude")
    evidence = pathlib.Path(args.evidence_dir).expanduser()
    if not evidence.is_absolute():
        evidence = pathlib.Path.cwd() / evidence
    evidence = evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)

    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = evidence / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    per_profile = run_dir / "profiles"
    per_profile.mkdir()

    system = {
        "run_id": run_id,
        "timestamp_utc": utc_now(),
        "cwd": str(pathlib.Path.cwd()),
        "repo_root": str(root),
        "profile_dir": str(profile_dir),
        "alt_claude": alt_claude,
        "binaries": [
            path_info("alt-claude"),
            path_info("alt-claude-core"),
            path_info("alt-claude-profile"),
            path_info("alt-claude-openai-bridge"),
            path_info("alt-claude-grok-bridge"),
            path_info("claude"),
            path_info("python3"),
        ],
        "git": {
            "branch": run_capture(["git", "branch", "--show-current"], root)["stdout"].strip(),
            "head": run_capture(["git", "rev-parse", "HEAD"], root)["stdout"].strip(),
            "status": run_capture(["git", "status", "--short"], root)["stdout"],
        },
        "safety": {
            "free_only": True,
            "fallback_disabled": True,
            "ignore_project_policy_for_probe": True,
            "record_use_disabled": True,
        },
        "prompt": PROMPT,
        "expected": EXPECTED,
    }
    write_json(run_dir / "system.json", system)

    catalog: list[dict[str, Any]] = []
    selected: list[tuple[pathlib.Path, dict[str, str]]] = []
    for path in sorted(profile_dir.glob("*.env")):
        meta = parse_env(path)
        row = {
            "profile": path.stem,
            "provider": meta.get("PROVIDER"),
            "model": meta.get("MODEL"),
            "logical_model": meta.get("LOGICAL_MODEL"),
            "status": meta.get("STATUS"),
            "privacy": meta.get("PRIVACY"),
            "free": is_free(meta),
        }
        catalog.append(row)
        if row["free"]:
            selected.append((path, meta))
    write_json(run_dir / "catalog.json", catalog)

    results: list[dict[str, Any]] = []
    for index, (path, meta) in enumerate(selected, 1):
        name = path.stem
        print(f"[{index}/{len(selected)}] testando {name} ...", flush=True)
        pdir = per_profile / name
        pdir.mkdir()

        command = [alt_claude, "--profile", name, "-p", PROMPT, "--output-format", "json"]
        (pdir / "command.txt").write_text(shlex.join(command) + "\n", encoding="utf-8")
        write_json(pdir / "profile.json", {
            "profile": name,
            "provider": meta.get("PROVIDER"),
            "model": meta.get("MODEL"),
            "logical_model": meta.get("LOGICAL_MODEL"),
            "status": meta.get("STATUS"),
            "privacy": meta.get("PRIVACY"),
            "free": is_free(meta),
        })

        env = os.environ.copy()
        env.update({
            "ALT_CLAUDE_PROFILE_DIR": str(profile_dir),
            "ALT_CLAUDE_NO_FALLBACK": "1",
            "ALT_CLAUDE_NO_RECORD_USE": "1",
            "ALT_CLAUDE_IGNORE_PROJECT_POLICY": "1",
            "CLAUDE_CODE_MAX_RETRIES": "0",
        })

        started = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(command, cwd=str(root), env=env, text=True, capture_output=True, timeout=args.timeout)
            returncode: int | None = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            returncode = 124
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            stderr += f"\nTIMEOUT after {args.timeout}s\n"

        seconds = round(time.monotonic() - started, 3)
        (pdir / "stdout.txt").write_text(stdout, encoding="utf-8")
        (pdir / "stderr.txt").write_text(stderr, encoding="utf-8")
        (pdir / "exit-code.txt").write_text(str(returncode) + "\n", encoding="utf-8")
        (pdir / "duration-seconds.txt").write_text(f"{seconds:.3f}\n", encoding="utf-8")

        answer, api_error = parse_answer(stdout)
        answer_score = score(answer)
        status = classify(returncode, stdout, stderr)
        if api_error:
            status = "api-error"
        elif answer is not None:
            status = "ok" if returncode == 0 and answer_score == 3 else f"partial-{answer_score}/3"

        result = {
            "profile": name,
            "provider": meta.get("PROVIDER"),
            "model": meta.get("MODEL"),
            "logical_model": meta.get("LOGICAL_MODEL"),
            "seconds": seconds,
            "returncode": returncode,
            "timed_out": timed_out,
            "status": status,
            "answered": answer is not None,
            "score": answer_score,
            "tests": 3 if answer is not None else 0,
            "api_error": api_error,
        }
        write_json(pdir / "result.json", result)
        results.append(result)

    ranked = sorted(
        results,
        key=lambda row: (
            0 if row["answered"] else 1,
            -(row["score"] if isinstance(row["score"], int) else -1),
            row["seconds"],
            row["profile"],
        ),
    )
    write_json(run_dir / "summary.json", ranked)

    tsv = ["rank\tprofile\tprovider\tmodel\tscore\tseconds\tstatus\treturncode"]
    md = [
        "# alt-claude free-model evidence",
        "",
        f"run: {run_id}",
        f"git: {system['git']['head']}",
        f"branch: {system['git']['branch']}",
        f"profiles tested: {len(ranked)}",
        "cost policy: free profiles only; fallback disabled",
        "project policy: ignored only for diagnostic probe",
        "",
        "| # | Profile | Provider | Model | Score | Seconds | Status |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for rank, row in enumerate(ranked, 1):
        score_text = f"{row['score']}/3" if row["answered"] else "-"
        tsv.append("\t".join([
            str(rank), str(row["profile"]), str(row["provider"] or ""),
            str(row["model"] or ""), score_text, f"{row['seconds']:.3f}",
            str(row["status"]), str(row["returncode"]),
        ]))
        md.append(
            f"| {rank} | {row['profile']} | {row['provider']} | {row['model']} | "
            f"{score_text} | {row['seconds']:.3f} | {row['status']} |"
        )

    (run_dir / "summary.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8")
    (run_dir / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (evidence / "LATEST").write_text(run_id + "\n", encoding="utf-8")

    print()
    print(f"Evidencias: {run_dir}")
    print(f"Resumo:     {run_dir / 'SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
