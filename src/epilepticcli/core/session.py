"""Session persistence: JSONL transcripts + markdown export."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from epilepticcli.config import SESSIONS_DIR


@dataclass
class Session:
    id: str
    provider: str
    model: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    input_tokens: int = 0
    output_tokens: int = 0

    @staticmethod
    def new(provider: str, model: str) -> Session:
        sid = time.strftime("%Y%m%d-%H%M%S")
        return Session(id=sid, provider=provider, model=model)

    @property
    def path(self) -> Path:
        return SESSIONS_DIR / f"{self.id}.jsonl"

    def save(self) -> None:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        header = {
            "type": "meta",
            "id": self.id,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
        lines = [json.dumps(header, ensure_ascii=False)]
        for m in self.messages:
            lines.append(json.dumps({"type": "message", "data": m}, ensure_ascii=False))
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, session_id: str) -> Session:
        path = SESSIONS_DIR / f"{session_id}.jsonl"
        meta: dict[str, Any] = {}
        messages: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("type") == "meta":
                meta = rec
            elif rec.get("type") == "message":
                messages.append(rec["data"])
        return cls(
            id=meta.get("id", session_id),
            provider=meta.get("provider", "?"),
            model=meta.get("model", "?"),
            messages=messages,
            created_at=meta.get("created_at", time.time()),
            input_tokens=meta.get("input_tokens", 0),
            output_tokens=meta.get("output_tokens", 0),
        )

    def export_markdown(self) -> Path:
        out = SESSIONS_DIR / f"{self.id}.md"
        parts = [f"# EpilepticCLI session {self.id}\n", f"`{self.provider} / {self.model}`\n"]
        for m in self.messages:
            role = m.get("role")
            if role == "user":
                parts.append(f"\n## ▚ You\n\n{m.get('content', '')}\n")
            elif role == "assistant":
                if m.get("content"):
                    parts.append(f"\n## ⌬ EpilepticCLI\n\n{m['content']}\n")
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function", {})
                    parts.append(f"\n> ◈ `{fn.get('name')}`\n")
            elif role == "tool":
                content = str(m.get("content", ""))
                parts.append(f"\n> ◈ tool result ({len(content)} chars)\n")
        out.write_text("".join(parts), encoding="utf-8")
        return out


def list_sessions() -> list[dict[str, Any]]:
    if not SESSIONS_DIR.is_dir():
        return []
    out = []
    for f in sorted(SESSIONS_DIR.glob("*.jsonl"), reverse=True):
        try:
            first = f.read_text(encoding="utf-8").splitlines()[0]
            meta = json.loads(first)
            meta["file"] = f.stem
            out.append(meta)
        except (IndexError, json.JSONDecodeError, OSError):
            continue
    return out
