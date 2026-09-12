#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOTS = [Path.home()/'.claude/projects', Path.home()/'.config/claude/projects']


def find_session(sid: str) -> Path:
    hits: list[Path] = []
    for root in ROOTS:
        if root.exists():
            hits += list(root.glob(f'**/{sid}.jsonl'))
    if not hits:
        raise FileNotFoundError(f'sessão {sid!r} não encontrada em ~/.claude/projects')
    return max(hits, key=lambda p: p.stat().st_mtime)


def load(path: Path) -> list[dict[str, Any]]:
    out = []
    with path.open(encoding='utf-8', errors='replace') as fh:
        for line in fh:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                out.append(item)
    return out


def blocks(rec: dict[str, Any]) -> list[dict[str, Any]]:
    msg = rec.get('message')
    if not isinstance(msg, dict):
        return []
    value = msg.get('content')
    if isinstance(value, str):
        return [{'type': 'text', 'text': value}]
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def texts(rec: dict[str, Any]) -> list[str]:
    return [b['text'].strip() for b in blocks(rec)
            if b.get('type') == 'text' and isinstance(b.get('text'), str) and b['text'].strip()]


def usage_tokens(records: list[dict[str, Any]]) -> int | None:
    latest = None
    for rec in records:
        msg = rec.get('message')
        usage = msg.get('usage') if isinstance(msg, dict) else None
        if not isinstance(usage, dict):
            continue
        total = 0
        found = False
        for key in ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'):
            value = usage.get(key)
            if isinstance(value, (int, float)):
                total += int(value)
                found = True
        if found:
            latest = total
    if latest is not None:
        return latest
    chars = sum(len(t) for rec in records for t in texts(rec))
    return chars // 4 if chars else None


def shorten(text: str, limit: int) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) <= limit else text[:limit-1].rstrip() + '…'


def metadata(records: list[dict[str, Any]]) -> dict[str, str]:
    data: dict[str, str] = {}
    for rec in records:
        for key in ('cwd', 'gitBranch', 'sessionId'):
            value = rec.get(key)
            if isinstance(value, str) and value:
                data[key] = value
    return data


def file_paths(records: list[dict[str, Any]]) -> list[str]:
    counts: Counter[str] = Counter()
    for rec in records:
        for block in blocks(rec):
            if block.get('type') != 'tool_use' or not isinstance(block.get('input'), dict):
                continue
            inp = block['input']
            for key in ('file_path', 'path', 'filepath', 'filename'):
                value = inp.get(key)
                if isinstance(value, str) and value:
                    counts[value] += 3
    return [p for p, _ in counts.most_common(30)]


def commands(records: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for rec in records:
        for block in blocks(rec):
            if block.get('type') != 'tool_use':
                continue
            name = str(block.get('name', '')).lower()
            inp = block.get('input')
            if name not in {'bash', 'shell', 'terminal', 'exec', 'run_command'} or not isinstance(inp, dict):
                continue
            cmd = inp.get('command') or inp.get('cmd')
            if isinstance(cmd, str):
                cmd = shorten(cmd, 500)
                if cmd not in seen:
                    seen.append(cmd)
    return seen[-20:]


def dialogue(records: list[dict[str, Any]], turns: int, chars: int) -> list[tuple[str, str]]:
    out = []
    for rec in records:
        kind = rec.get('type')
        if kind not in {'user', 'assistant'}:
            continue
        text = '\n'.join(texts(rec)).strip()
        if text:
            out.append(('Usuário' if kind == 'user' else 'Assistente', shorten(text, chars)))
    return out[-turns:]


def render(sid: str, source: Path, records: list[dict[str, Any]], turns: int, chars: int) -> str:
    meta = metadata(records)
    tokens = usage_tokens(records)
    out = ['# Claude Code session handoff', '', f'- Session ID: `{sid}`', f'- Source: `{source}`']
    if meta.get('cwd'):
        out.append(f"- Working directory: `{meta['cwd']}`")
    if meta.get('gitBranch'):
        out.append(f"- Git branch: `{meta['gitBranch']}`")
    if tokens is not None:
        out.append(f'- Last observed/estimated context: ~{tokens:,} tokens')
    out += [f'- Transcript records: {len(records):,}', '', '## Files/paths seen', '']
    paths = file_paths(records)
    out += [f'- `{p}`' for p in paths] if paths else ['- None inferred.']
    out += ['', '## Recent shell commands', '']
    cmds = commands(records)
    out += [f"- `{c.replace('`', chr(39))}`" for c in cmds] if cmds else ['- None inferred.']
    out += ['', '## Recent conversation', '']
    for role, text in dialogue(records, turns, chars):
        out += [f'### {role}', text, '']
    out += [
        '## Continuation instruction', '',
        'Continue from this handoff. First inspect the current repository state, git status, relevant files and tests.',
        'This is a lossy offline recovery artifact; the current filesystem and repository are authoritative.', ''
    ]
    return '\n'.join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description='Create an offline Markdown handoff from a Claude Code session')
    ap.add_argument('session_id')
    ap.add_argument('-o', '--output')
    ap.add_argument('--turns', type=int, default=24)
    ap.add_argument('--message-chars', type=int, default=1800)
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--max-tokens', type=int)
    args = ap.parse_args()
    try:
        source = find_session(args.session_id)
        records = load(source)
    except OSError as exc:
        print(f'Erro: {exc}', file=sys.stderr)
        return 2
    tokens = usage_tokens(records)
    if args.status:
        print(f'session={args.session_id} tokens={tokens or 0} source={source}')
        return 75 if args.max_tokens and tokens is not None and tokens >= args.max_tokens else 0
    output = Path(os.path.expanduser(args.output)).resolve() if args.output else Path.cwd()/f'claude-handoff-{args.session_id}.md'
    output.write_text(render(args.session_id, source, records, max(4, args.turns), max(300, args.message_chars)), encoding='utf-8')
    print(output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
