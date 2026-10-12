#!/usr/bin/env python3
"""Shared model state for alt-claude.

Project-local "last model" is keyed by the current Git root. Evaluation and
model enable/disable state are global so quality decisions carry across repos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_root() -> pathlib.Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception as exc:
        raise RuntimeError("diretório atual não pertence a um repositório Git") from exc
    if not out:
        raise RuntimeError("não foi possível determinar a raiz Git")
    return pathlib.Path(out).resolve()


def project_key(root: pathlib.Path) -> str:
    return hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:20]


def project_last_path(root: pathlib.Path) -> pathlib.Path:
    return STATE_ROOT / "projects" / project_key(root) / "last-model.json"


def atomic_write_json(path: pathlib.Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def append_jsonl(path: pathlib.Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.chmod(path, 0o600)


def disabled_path() -> pathlib.Path:
    return CONFIG_ROOT / "disabled-models.json"


def load_disabled() -> dict[str, Any]:
    path = disabled_path()
    if not path.exists():
        return {"version": 1, "models": {}}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "models": {}}
    if not isinstance(obj, dict):
        return {"version": 1, "models": {}}
    models = obj.get("models")
    if not isinstance(models, dict):
        models = {}
    return {"version": 1, "models": models}


def save_disabled(obj: dict[str, Any]) -> None:
    CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    atomic_write_json(disabled_path(), obj)


def cmd_record_use(args: argparse.Namespace) -> int:
    try:
        root = git_root()
    except RuntimeError:
        # Launching outside a repo is valid; there is simply no project-local
        # last-model pointer to update.
        root = None

    event = {
        "timestamp": now_iso(),
        "profile": args.profile or None,
        "provider": args.provider,
        "model": args.model,
        "route": args.route or args.provider,
    }
    if root is not None:
        event["project_key"] = project_key(root)
        event["project_root"] = str(root)
        atomic_write_json(project_last_path(root), event)
    append_jsonl(STATE_ROOT / "usage.jsonl", event)
    return 0


def read_last() -> tuple[pathlib.Path, dict[str, Any]]:
    root = git_root()
    path = project_last_path(root)
    if not path.exists():
        raise RuntimeError(f"nenhum modelo registrado para este projeto: {root}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"registro inválido: {path}") from exc
    return root, obj


def cmd_last_model(args: argparse.Namespace) -> int:
    try:
        root, obj = read_last()
    except RuntimeError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    if args.json:
        out = dict(obj)
        out["project_root"] = str(root)
        print(json.dumps(out, ensure_ascii=False))
    else:
        profile = obj.get("profile")
        suffix = f" [{profile}]" if profile else ""
        print(f"{obj.get('model')} via {obj.get('provider')}{suffix}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    if args.rating < 1 or args.rating > 5:
        print("Erro: avaliação deve estar entre 1 e 5.", file=sys.stderr)
        return 2
    try:
        root, last = read_last()
    except RuntimeError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    event = {
        "timestamp": now_iso(),
        "rating": args.rating,
        "comment": args.comment or None,
        "model": last.get("model"),
        "provider": last.get("provider"),
        "profile": last.get("profile"),
        "route": last.get("route"),
        "source_project_key": project_key(root),
    }
    append_jsonl(STATE_ROOT / "evaluations.jsonl", event)
    if args.json:
        print(json.dumps(event, ensure_ascii=False))
    else:
        print(f"Avaliação {args.rating}/5 registrada para {event['model']} via {event['provider']}.")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    obj = load_disabled()
    obj["models"][args.model] = {
        "disabled_at": now_iso(),
        "label": args.label or args.model,
        "reason": args.reason or None,
    }
    save_disabled(obj)
    print(f"Modelo desabilitado: {args.model}")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    obj = load_disabled()
    existed = args.model in obj["models"]
    obj["models"].pop(args.model, None)
    save_disabled(obj)
    if existed:
        print(f"Modelo habilitado: {args.model}")
    else:
        print(f"Modelo já estava habilitado: {args.model}")
    return 0


def cmd_check_enabled(args: argparse.Namespace) -> int:
    obj = load_disabled()
    info = obj["models"].get(args.model)
    if not info:
        return 0
    label = info.get("label") or args.model
    print(
        f"ALERTA: modelo desabilitado: {label} ({args.model}). "
        f"Use 'alt-claude --enable {label}' para habilitá-lo.",
        file=sys.stderr,
    )
    if info.get("reason"):
        print(f"Motivo: {info['reason']}", file=sys.stderr)
    return 78


def cmd_list_disabled(args: argparse.Namespace) -> int:
    obj = load_disabled()
    models = obj["models"]
    if args.json:
        print(json.dumps(models, ensure_ascii=False))
        return 0
    if not models:
        print("Nenhum modelo desabilitado.")
        return 0
    for model, info in sorted(models.items()):
        label = info.get("label") or model
        reason = info.get("reason")
        tail = f" — {reason}" if reason else ""
        print(f"{label}: {model}{tail}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("record-use")
    q.add_argument("--profile", default="")
    q.add_argument("--provider", required=True)
    q.add_argument("--model", required=True)
    q.add_argument("--route", default="")
    q.set_defaults(func=cmd_record_use)

    q = sub.add_parser("last-model")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_last_model)

    q = sub.add_parser("evaluate")
    q.add_argument("rating", type=int)
    q.add_argument("--comment", default="")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_evaluate)

    q = sub.add_parser("disable")
    q.add_argument("model")
    q.add_argument("--label", default="")
    q.add_argument("--reason", default="")
    q.set_defaults(func=cmd_disable)

    q = sub.add_parser("enable")
    q.add_argument("model")
    q.set_defaults(func=cmd_enable)

    q = sub.add_parser("check-enabled")
    q.add_argument("model")
    q.set_defaults(func=cmd_check_enabled)

    q = sub.add_parser("list-disabled")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_list_disabled)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
