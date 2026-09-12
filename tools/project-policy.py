#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import subprocess
from pathlib import Path

KEYS = {
    "mode": "standard",
    "deny_profiles": "",
    "allow_profiles": "",
    "deny_providers": "",
    "deny_privacy": "public_only",
}


def project_root() -> Path:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL, text=True).strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return Path.cwd()


def config_path() -> Path:
    return project_root() / ".alt-claude" / "config"


def parse(path: Path) -> dict[str, str]:
    cfg = dict(KEYS)
    if not path.exists():
        return cfg
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().lower()
        if k in cfg:
            cfg[k] = v.strip()
    return cfg


def csv(value: str) -> set[str]:
    return {x.strip() for x in value.split(",") if x.strip()}


def write(cfg: dict[str, str]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = """# alt-claude project policy\n# This file is declarative and is never sourced as shell code.\n"""
    for k in KEYS:
        text += f"{k}={cfg.get(k, KEYS[k])}\n"
    path.write_text(text, encoding="utf-8")
    print(path)


def cmd_init(preset: str) -> int:
    cfg = dict(KEYS)
    if preset == "sensitive":
        cfg["mode"] = "sensitive"
        cfg["deny_privacy"] = "review,public_only"
    write(cfg)
    return 0


def cmd_show() -> int:
    path = config_path()
    cfg = parse(path)
    print(f"project={project_root()}")
    print(f"config={path}{'' if path.exists() else ' (not created)'}")
    for k in KEYS:
        print(f"{k}={cfg[k]}")
    return 0


def mutate(action: str, kind: str, value: str) -> int:
    cfg = parse(config_path())
    key = {("deny", "profile"): "deny_profiles", ("allow", "profile"): "allow_profiles", ("deny", "provider"): "deny_providers"}.get((action, kind))
    if not key:
        raise SystemExit("supported: deny profile|provider; allow profile")
    values = csv(cfg[key])
    values.add(value)
    cfg[key] = ",".join(sorted(values))
    write(cfg)
    return 0


def check(profile: str, provider: str, privacy: str) -> int:
    path = config_path()
    cfg = parse(path)
    denies_p = csv(cfg["deny_profiles"])
    allows_p = csv(cfg["allow_profiles"])
    denies_provider = csv(cfg["deny_providers"])
    denies_privacy = csv(cfg["deny_privacy"])

    reason = None
    if profile and profile in denies_p:
        reason = f"profile '{profile}' is denied"
    elif provider and provider in denies_provider:
        reason = f"provider '{provider}' is denied"
    elif profile and profile in allows_p:
        return 0
    elif privacy in denies_privacy:
        reason = f"privacy class '{privacy}' is denied"
    elif cfg["mode"] == "sensitive" and privacy != "sensitive_ok":
        reason = f"sensitive mode requires privacy=sensitive_ok (got {privacy})"

    if reason:
        print("alt-claude: BLOCKED by project policy", file=os.sys.stderr)
        print(f"alt-claude: {reason}", file=os.sys.stderr)
        print(f"alt-claude: policy: {path}", file=os.sys.stderr)
        return 77
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="alt-claude policy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("preset", choices=["standard", "sensitive"], nargs="?", default="standard")
    sub.add_parser("show")
    for action in ("deny", "allow"):
        p = sub.add_parser(action)
        p.add_argument("kind", choices=["profile", "provider"] if action == "deny" else ["profile"])
        p.add_argument("value")
    p = sub.add_parser("check")
    p.add_argument("--profile", default="")
    p.add_argument("--provider", default="")
    p.add_argument("--privacy", default="review", choices=["sensitive_ok", "review", "public_only"])
    args = ap.parse_args()
    if args.cmd == "init": return cmd_init(args.preset)
    if args.cmd == "show": return cmd_show()
    if args.cmd in {"deny", "allow"}: return mutate(args.cmd, args.kind, args.value)
    if args.cmd == "check": return check(args.profile, args.provider, args.privacy)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
