#!/usr/bin/env python3
"""Minimal Anthropic Messages -> OpenAI-compatible Chat Completions bridge for Claude Code.

The bridge keeps an arbitrary OpenAI-compatible provider behind a localhost
Anthropic-compatible surface so Claude Code remains the console/UI.

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
import urllib.error
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


UPSTREAM_BASE_URL = os.environ.get("OPENAI_COMPAT_BASE_URL", "").rstrip("/")
UPSTREAM_API_KEY = os.environ.get("OPENAI_COMPAT_API_KEY", "")
DEFAULT_MODEL = os.environ.get("OPENAI_COMPAT_MODEL", "")
UPSTREAM_NAME = os.environ.get("OPENAI_COMPAT_NAME", "openai-compatible").strip() or "openai-compatible"


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return "" if content is None else str(content)
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            kind = block.get("type")
            if kind in {"text", "input_text", "output_text"}:
                parts.append(str(block.get("text", "")))
            elif kind == "tool_result":
                parts.append(_text_from_content(block.get("content", "")))
    return "\n".join(x for x in parts if x)


def _openai_user_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return _text_from_content(content)

    out: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            out.append({"type": "text", "text": str(block)})
            continue
        kind = block.get("type")
        if kind == "text":
            out.append({"type": "text", "text": str(block.get("text", ""))})
        elif kind == "image":
            source = block.get("source") or {}
            if source.get("type") == "base64" and source.get("data"):
                media_type = source.get("media_type", "image/png")
                out.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{source['data']}"},
                })
    if not out:
        return _text_from_content(content)
    if len(out) == 1 and out[0].get("type") == "text":
        return out[0]["text"]
    return out


def _messages_to_openai(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    system = payload.get("system")
    system_text = _text_from_content(system)
    if system_text:
        result.append({"role": "system", "content": system_text})

    for msg in payload.get("messages") or []:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "assistant":
            if isinstance(content, str):
                result.append({"role": "assistant", "content": content})
                continue
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            for block in content or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text_parts.append(str(block.get("text", "")))
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": str(block.get("id") or f"call_{uuid.uuid4().hex[:24]}"),
                        "type": "function",
                        "function": {
                            "name": str(block.get("name", "")),
                            "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
                        },
                    })
            item: dict[str, Any] = {
                "role": "assistant",
                "content": "\n".join(text_parts) if text_parts else None,
            }
            if tool_calls:
                item["tool_calls"] = tool_calls
            result.append(item)
            continue

        if role == "user" and isinstance(content, list):
            tool_results = [
                block for block in content
                if isinstance(block, dict) and block.get("type") == "tool_result"
            ]
            normal_blocks = [
                block for block in content
                if not (isinstance(block, dict) and block.get("type") == "tool_result")
            ]
            for block in tool_results:
                result.append({
                    "role": "tool",
                    "tool_call_id": str(block.get("tool_use_id", "")),
                    "content": _text_from_content(block.get("content", "")),
                })
            if normal_blocks:
                result.append({"role": "user", "content": _openai_user_content(normal_blocks)})
            continue

        result.append({"role": role or "user", "content": _openai_user_content(content)})
    return result


def _tools_to_openai(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tool in payload.get("tools") or []:
        if not isinstance(tool, dict) or not tool.get("name"):
            continue
        fn: dict[str, Any] = {
            "name": tool["name"],
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        }
        if tool.get("description"):
            fn["description"] = tool["description"]
        out.append({"type": "function", "function": fn})
    return out


def _tool_choice_to_openai(choice: Any) -> Any:
    if not isinstance(choice, dict):
        return None
    kind = choice.get("type")
    if kind == "auto":
        return "auto"
    if kind == "any":
        return "required"
    if kind == "tool" and choice.get("name"):
        return {"type": "function", "function": {"name": choice["name"]}}
    return None


def _request_upstream(payload: dict[str, Any]) -> dict[str, Any]:
    if not UPSTREAM_BASE_URL:
        raise RuntimeError("OPENAI_COMPAT_BASE_URL is not configured")
    if not DEFAULT_MODEL:
        raise RuntimeError("OPENAI_COMPAT_MODEL is not configured")

    model = payload.get("model") or DEFAULT_MODEL
    body: dict[str, Any] = {
        "model": model,
        "messages": _messages_to_openai(payload),
        # Keep the upstream call synchronous. When Claude requests streaming,
        # the bridge synthesizes Anthropic SSE after the complete xAI response.
        "stream": False,
    }
    tools = _tools_to_openai(payload)
    if tools:
        body["tools"] = tools
        choice = _tool_choice_to_openai(payload.get("tool_choice"))
        if choice is not None:
            body["tool_choice"] = choice

    max_tokens = payload.get("max_tokens")
    if isinstance(max_tokens, int) and max_tokens > 0:
        body["max_tokens"] = max_tokens


    req = urllib.request.Request(
        UPSTREAM_BASE_URL + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            **({"Authorization": f"Bearer {UPSTREAM_API_KEY}"} if UPSTREAM_API_KEY else {}),
            "Content-Type": "application/json",
            "User-Agent": "alt-claude-openai-bridge/1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{UPSTREAM_NAME} HTTP {exc.code}: {raw[:4000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{UPSTREAM_NAME} connection error: {exc}") from exc
    return json.loads(raw)


def _anthropic_blocks(response: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    choices = response.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    blocks: list[dict[str, Any]] = []

    content = message.get("content")
    if content:
        blocks.append({"type": "text", "text": str(content)})

    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        args_raw = fn.get("arguments") or "{}"
        try:
            args = json.loads(args_raw)
        except Exception:
            args = {"_raw": args_raw}
        blocks.append({
            "type": "tool_use",
            "id": str(call.get("id") or f"call_{uuid.uuid4().hex[:24]}"),
            "name": str(fn.get("name", "")),
            "input": args,
        })

    finish = choice.get("finish_reason")
    if any(b.get("type") == "tool_use" for b in blocks):
        stop_reason = "tool_use"
    elif finish == "length":
        stop_reason = "max_tokens"
    else:
        stop_reason = "end_turn"
    return blocks, stop_reason


def _usage(response: dict[str, Any]) -> tuple[int, int]:
    usage = response.get("usage") or {}
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def _anthropic_message(payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    blocks, stop_reason = _anthropic_blocks(response)
    input_tokens, output_tokens = _usage(response)
    return {
        "id": "msg_" + uuid.uuid4().hex,
        "type": "message",
        "role": "assistant",
        "model": response.get("model") or payload.get("model") or DEFAULT_MODEL,
        "content": blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "alt-claude-openai-bridge/1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{UPSTREAM_NAME}-bridge] {self.address_string()} - {fmt % args}", flush=True)

    def _json(self, status: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        if path == "/v1/models":
            self._json(200, {
                "object": "list",
                "data": [{"id": DEFAULT_MODEL, "object": "model", "owned_by": UPSTREAM_NAME}],
            })
            return
        if path in {"", "/health", "/v1/health"}:
            self._json(200, {"ok": True, "model": DEFAULT_MODEL})
            return
        self._json(404, {"error": {"type": "not_found_error", "message": "not found"}})

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception as exc:
            self._json(400, {"type": "error", "error": {"type": "invalid_request_error", "message": str(exc)}})
            return

        if path == "/v1/messages/count_tokens":
            # Conservative local estimate. Claude Code mainly needs a bounded
            # count here; actual billing usage comes from xAI responses.
            text = json.dumps(payload.get("messages") or [], ensure_ascii=False)
            text += _text_from_content(payload.get("system"))
            self._json(200, {"input_tokens": max(1, len(text) // 4)})
            return

        if path != "/v1/messages":
            self._json(404, {"type": "error", "error": {"type": "not_found_error", "message": "not found"}})
            return

        try:
            response = _request_upstream(payload)
            message = _anthropic_message(payload, response)
        except Exception as exc:
            self._json(502, {
                "type": "error",
                "error": {"type": "api_error", "message": str(exc)},
            })
            return

        if not payload.get("stream"):
            self._json(200, message)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        input_tokens = int(message["usage"]["input_tokens"])
        output_tokens = int(message["usage"]["output_tokens"])
        start_message = dict(message)
        start_message["content"] = []
        start_message["stop_reason"] = None
        start_message["usage"] = {"input_tokens": input_tokens, "output_tokens": 0}
        self._event("message_start", {"type": "message_start", "message": start_message})

        for idx, block in enumerate(message["content"]):
            if block.get("type") == "text":
                self._event("content_block_start", {
                    "type": "content_block_start",
                    "index": idx,
                    "content_block": {"type": "text", "text": ""},
                })
                self._event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {"type": "text_delta", "text": block.get("text", "")},
                })
            elif block.get("type") == "tool_use":
                self._event("content_block_start", {
                    "type": "content_block_start",
                    "index": idx,
                    "content_block": {
                        "type": "tool_use",
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "input": {},
                    },
                })
                self._event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(block.get("input") or {}, ensure_ascii=False),
                    },
                })
            self._event("content_block_stop", {"type": "content_block_stop", "index": idx})

        self._event("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": message["stop_reason"], "stop_sequence": None},
            "usage": {"output_tokens": output_tokens},
        })
        self._event("message_stop", {"type": "message_stop"})
        self.close_connection = True

    def _event(self, name: str, data: dict[str, Any]) -> None:
        raw = f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")
        self.wfile.write(raw)
        self.wfile.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("ALT_CLAUDE_OPENAI_BRIDGE_PORT", "8790")))
    args = parser.parse_args()

    if not UPSTREAM_BASE_URL:
        raise SystemExit("OPENAI_COMPAT_BASE_URL is required")
    if not DEFAULT_MODEL:
        raise SystemExit("OPENAI_COMPAT_MODEL is required")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"[{UPSTREAM_NAME}-bridge] listening on http://{args.host}:{args.port} -> "
        f"{UPSTREAM_BASE_URL} model={DEFAULT_MODEL}",
        flush=True,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
