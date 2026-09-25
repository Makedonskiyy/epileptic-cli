"""Tool framework: specs, results, and the registry the agent loop dispatches on."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    content: str
    is_error: bool = False


ToolFunc = Callable[..., ToolResult]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: ToolFunc
    needs_approval: bool = False
    summarize: Callable[[dict[str, Any]], str] | None = None

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def summary_line(self, args: dict[str, Any]) -> str:
        if self.summarize:
            try:
                return self.summarize(args)
            except Exception:
                pass
        return ", ".join(f"{k}={str(v)[:60]!r}" for k, v in args.items())


def obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


def trunc(text: str, limit: int = 50_000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... [truncated at {limit} chars]"


def resolve_path(p: str, cwd: Path) -> Path:
    path = Path(p).expanduser()
    if not path.is_absolute():
        path = cwd / path
    return path
