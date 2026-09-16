#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

CRED_DIR = Path(os.environ.get("ALT_CLAUDE_CREDENTIALS_DIR", "~/.config/credentials/personal/ai")).expanduser()

KEY_HELP = {
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/settings/keys"),
    "groq": ("GROQ_API_KEY", "https://console.groq.com/keys"),
    "nvidia": ("NVIDIA_API_KEY", "https://build.nvidia.com/settings/api-keys"),
    "grok": ("GROK_API_KEY", "https://console.x.ai/"),
    "kimi": ("KIMI_API_KEY", "https://www.kimi.com/code"),
}


def load_env(name: str) -> dict[str, str]:
    path = CRED_DIR / f"{name}.env"
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        values[k.strip()] = v
    return values


def http_json(url: str, headers: dict[str, str], method: str = "GET", data: bytes | None = None) -> tuple[int | None, dict]:
    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(raw)
            except Exception:
                return response.status, {}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            body = {}
        return exc.code, body
    except Exception:
        return None, {}


def cmd(*args: str) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=15, check=False).stdout.strip()
    except Exception:
        return ""


def row(provider: str, auth: str, quota: str, detail: str) -> None:
    print(f"{provider:<12} {auth:<12} {quota:<16} {detail}")


def openrouter() -> None:
    env = load_env("openrouter")
    key = env.get("OPENROUTER_API_KEY", "")
    if not key:
        row("openrouter", "SEM CHAVE", "DESCONHECIDA", "crie a chave com: alt-claude help keys")
        return
    status, body = http_json("https://openrouter.ai/api/v1/key", {"Authorization": f"Bearer {key}"})
    if status != 200:
        row("openrouter", f"HTTP {status or 'ERR'}", "DESCONHECIDA", "a chave não pôde ser validada")
        return
    data = body.get("data") if isinstance(body, dict) else {}
    data = data if isinstance(data, dict) else {}
    monthly = data.get("usage_monthly")
    total = data.get("usage")
    remaining = data.get("limit_remaining")
    parts = []
    if monthly is not None:
        parts.append(f"uso-mês=US${float(monthly):.4f}")
    if total is not None:
        parts.append(f"uso-total=US${float(total):.4f}")
    if remaining is not None:
        parts.append(f"limite-chave-restante=US${float(remaining):.4f}")
    detail = ", ".join(parts) if parts else "endpoint de chave respondeu, mas sem campos de uso"
    row("openrouter", "VÁLIDA", "PARCIAL", detail + "; rate-limit diário restante não é exposto aqui")


def simple_key_provider(name: str, var: str, url: str, note: str) -> None:
    env = load_env(name)
    key = env.get(var, "")
    if not key:
        row(name, "SEM CHAVE", "DESCONHECIDA", "crie a chave com: alt-claude help keys")
        return
    status, _ = http_json(url, {"Authorization": f"Bearer {key}"})
    if status == 200:
        row(name, "VÁLIDA", "DESCONHECIDA", note)
    else:
        row(name, f"HTTP {status or 'ERR'}", "DESCONHECIDA", "a chave não pôde ser validada")


def codex() -> None:
    binary = shutil.which("claude-codex-proxy")
    if not binary:
        row("codex", "N/D", "DESCONHECIDA", "claude-codex-proxy não instalado")
        return
    text = cmd(binary, "accounts", "list")
    if "No accounts configured" in text:
        row("codex", "SEM CONTA", "DESCONHECIDA", "nenhuma conta configurada")
    elif text:
        row("codex", "CONFIGURADA", "DESCONHECIDA", "o proxy confirma conta local, mas não expõe quota restante de forma confiável")
    else:
        row("codex", "N/D", "DESCONHECIDA", "não foi possível confirmar conta nem quota")


def copilot() -> None:
    if not shutil.which("npx") or not shutil.which("node"):
        row("copilot", "N/D", "DESCONHECIDA", "node/npx indisponível")
        return
    preferred = Path(os.environ.get("COPILOT_API_HOME", str(CRED_DIR / "copilot-api"))).expanduser()
    legacy = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "copilot-api"
    api_home = preferred if (preferred / "config.json").exists() or (preferred / "github_token").exists() else legacy
    try:
        p = subprocess.run(
            ["npx", "--yes", "@jeffreycao/copilot-api@latest", "debug", "--api-home", str(api_home), "--json"],
            capture_output=True, text=True, timeout=20, check=False
        )
        text = p.stdout
        i = text.find("{")
        payload = json.loads(text[i:]) if i >= 0 else {}
        ok = payload.get("tokenExists") is True or bool((payload.get("providers") or {}).get("enabled"))
    except Exception:
        ok = False
    if ok:
        row("copilot", "CONFIGURADA", "DESCONHECIDA", "autenticação local existe; quota/requests restantes não são expostos pelo wrapper")
    else:
        row("copilot", "N/D", "DESCONHECIDA", "não foi possível confirmar autenticação")


def main() -> int:
    print(f"Credenciais: {CRED_DIR}")
    print()
    print(f"{'PROVEDOR':<12} {'AUTH':<12} {'QUOTA':<16} DETALHE")
    print(f"{'-'*12} {'-'*12} {'-'*16} {'-'*60}")
    copilot()
    codex()
    openrouter()
    simple_key_provider("grok", "GROK_API_KEY", "https://api.x.ai/v1/models", "a API pública valida a chave; saldo/quota restante exige dados de billing/management não disponíveis nesta integração")
    simple_key_provider("nvidia", "NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1/models", "a chave funciona; a API de modelos não informa quota restante do endpoint gratuito")
    simple_key_provider("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1/models", "a chave funciona; limites publicados não equivalem a quota restante, que deve ser vista no console")
    # Kimi Code não tem health endpoint de quota confiável sem potencialmente fazer inferência.
    kimi_env = load_env("kimi")
    if kimi_env.get("KIMI_API_KEY"):
        row("kimi", "PRESENTE", "DESCONHECIDA", "não fazemos chamada de inferência no --usage; presença da chave não prova saldo nem acesso ao Kimi Code")
    else:
        row("kimi", "SEM CHAVE", "DESCONHECIDA", "Kimi Code pode exigir plano/crédito; veja alt-claude help keys")
    print()
    print("Legenda: VÁLIDA/CONFIGURADA confirma autenticação ou configuração, NÃO confirma saldo disponível.")
    print("         DESCONHECIDA significa exatamente isso: alt-claude não consegue medir a quota restante com fidelidade.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
