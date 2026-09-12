#!/usr/bin/env python3
"""Offline Claude Code session handoff generator.

Reads ~/.claude/projects/**/<session-id>.jsonl without calling any model/API and
produces a compact Markdown handoff for starting a fresh session.

The Claude Code JSONL schema is not formally stable, so parsing is deliberately
lenient and ignores unknown record/block types.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

HOME = Path.home()
DEFAULT_ROOTS = [HOME / ".claude" / "projects", HOME / ".config" / "claude" / "projects"]


def find_session(session_id: str, roots: Iterable[Path]) -> Path:
    target = f"{session_id}.jsonl"
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        found.extend(root.glob(f"**/{target}"))
    if not found:
        raise FileNotFoundError(f"sessão {session_id!r} não encontrada em ~/.claude/projects")
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[0]


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
    return records


def blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    msg = record.get("message")
    if not isinstance(msg, dict):
        return []
    content = msg.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [x for x in content if isinstance(x, dict)]
    return []


def text_blocks(record: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for block in blocks(record):
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            text = block["text"].strip()
            if text:
                out.append(text)
    return out


def tool_uses(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [b for b in blocks(record) if b.get("type") == "tool_use"]


def estimate_tokens(records: list[dict[str, Any]]) -> int | None:
    """Prefer provider-reported latest request context; fall back to char estimate."""
    best: int | None = None
    for rec in records:
        msg = rec.get("message")
        if not isinstance(msg, dict):
            continue
        usage = msg.get("usage")
        if not isinstance(usage, dict):
            continue
        vals = []
        for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
            value = usage.get(key)
            if isinstance(value, (int, float)):
                vals.append(int(value))
        if vals:
            best = sum(vals)
    if best is not None:
        return best
    chars = 0
    for rec in records:
        chars += sum(len(t) for t in text_blocks(rec))
    return max(1, chars // 4) if chars else None


def discover_metadata(records: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for rec in records:
        for key in ("cwd", "gitBranch", "sessionId"):
            value = rec.get(key)
            if isinstance(value, str) and value:
                result[key] = value
    return result


def shorten(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def collect_files(records: list[dict[str, Any]]) -> list[tuple[str, int]]:
    hits: Counter[str] = Counter()
    path_re = re.compile(r"(?<![\w.-])(?:\.?\.?/)?[\w.@+-]+(?:/[\w.@+ -]+)+\.[A-Za-z0-9_-]{1,12}")
    for rec in records:
        for use in tool_uses(rec):
            inp = use.get("input")
            if isinstance(inp, dict):
                for key in ("file_path", "path", "filepath", "filename"):
                    value = inp.get(key)
                    if isinstance(value, str) and value:
                        hits[value] += 3
                blob = json.dumps(inp, ensure_ascii=False)
                for match in path_re.findall(blob):
                    hits[match] += 1
        for text in text_blocks(rec):
            for match in path_re.findall(text):
                hits[match] += 1
    return hits.most_common(30)


def collect_commands(records: list[dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for rec in records:
        for use in tool_uses(rec):
            name = str(use.get("name", "")).lower()
            inp = use.get("input")
            if name not in {"bash", "shell", "terminal", "exec", "run_command"} or not isinstance(inp, dict):
                continue
            cmd = inp.get("command") or inp.get("cmd")
            if isinstance(cmd, str):
                cmd = shorten(cmd, 500)
                if cmd not in seen:
                    seen.add(cmd)
                    commands.append(cmd)
    return commands[-20:]


def recent_dialogue(records: list[dict[str, Any]], turns: int, per_message: int) -> list[tuple[str, str]]:
    messages: list[tuple[str, str]] = []
    for rec in records:
        kind = rec.get("type")
        if kind not in {"user", "assistant"}:
            continue
        text = "\n".join(text_blocks(rec)).strip()
        if not text:
            continue
        role = "Usuário" if kind == "user" else "Assistente"
        messages.append((role, shorten(text, per_message)))
    return messages[-turns:]


def compact_events(records: list[dict[str, Any]]) -> int:
    count = 0
    for rec in records:
        if "compactMetadata" in rec or rec.get("type") in {"summary", "compact"}:
            count += 1
    return count


def render(session_id: str, path: Path, records: list[dict[str, Any]], turns: int, per_message: int) -> str:
    meta = discover_metadata(records)
    token_estimate = estimate_tokens(records)
    files = collect_files(records)
    commands = collect_commands(records)
    dialogue = recent_dialogue(records, turns, per_message)

    lines = [
        "# Claude Code session handoff",
        "",
        f"- Session ID: `{session_id}`",
        f"- Source: `{path}`",
    ]
    if meta.get("cwd"):
        lines.append(f"- Working directory: `{meta['cwd']}`")
    if meta.get("gitBranch"):
        lines.append(f"- Git branch: `{meta['gitBranch']}`")
    if token_estimate is not None:
        lines.append(f"- Last observed/estimated context: ~{token_estimate:,} tokens")
    lines.append(f"- Transcript records: {len(records):,}")
    lines.append(f"- Compaction-related records observed: {compact_events(records)}")

    lines += ["", "## Files and paths seen most often", ""]
    if files:
        for path_name, score in files:
            lines.append(f"- `{path_name}`")
    else:
        lines.append("- No file paths could be inferred.")

    lines += ["", "## Recent shell commands", ""]
    if commands:
        for cmd in commands:
            lines.append(f"- `{cmd.replace('`', "'")}`")
    else:
        lines.append("- No shell commands could be inferred.")

    lines += ["", "## Recent conversation", ""]
    for role, text in dialogue:
        lines.append(f"### {role}")
        lines.append(text)
        lines.append("")

    lines += [
        "## Continuation instruction",
        "",
        "Continue the work represented by this handoff. First inspect the repository state, git status,",
        "relevant files and tests before changing anything. Treat this handoff as a lossy recovery artifact:",
        "the repository and current filesystem are authoritative when they disagree with this summary.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact a Claude Code JSONL session offline into Markdown")
    parser.add_argument("session_id")
    parser.add_argument("--output", "-o", help="output Markdown path")
    parser.add_argument("--turns", type=int, default=24, help="number of recent user/assistant messages to keep")
    parser.add_argument("--message-chars", type=int, default=1800, help="max chars kept per recent message")
    parser.add_argument("--status", action="store_true", help="print token/context status only")
    parser.add_argument("--max-tokens", type=int, help="with --status, exit 75 when context is at/above this value")
    args = parser.parse_args()

    try:
        source = find_session(args.session_id, DEFAULT_ROOTS)
        records = load_records(source)
    except (OSError, FileNotFoundError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    tokens = estimate_tokens(records)
    if args.status:
        value = tokens if tokens is not None else 0
        print(f"session={args.session_id} tokens={value} source={source}")
        if args.max_tokens and tokens is not None and tokens >= args.max_tokens:
            return 75
        return 0

    text = render(args.session_id, source, records, max(4, args.turns), max(300, args.message_chars))
    if args.output:
        output = Path(os.path.expanduser(args.output)).resolve()
    else:
        output = Path.cwd() / f"claude-handoff-{args.session_id}.md"
    output.write_text(text, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
