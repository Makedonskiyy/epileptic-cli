"""Filesystem tools: read, write, edit, ls, glob, grep."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from epilepticcli.tools.base import Tool, ToolResult, obj, resolve_path, trunc

MAX_LINES = 2000


def make_tools(cwd: Path) -> list[Tool]:
    def read_file(path: str, offset: int = 0, limit: int = MAX_LINES) -> ToolResult:
        p = resolve_path(path, cwd)
        if not p.exists():
            return ToolResult(f"File not found: {p}", is_error=True)
        if p.is_dir():
            return ToolResult(f"{p} is a directory, use ls", is_error=True)
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            return ToolResult(f"Cannot read {p}: {e}", is_error=True)
        total = len(lines)
        chunk = lines[offset : offset + limit]
        body = "\n".join(f"{offset + i + 1}\t{ln}" for i, ln in enumerate(chunk))
        note = f"[{p}] {total} lines total"
        if offset + limit < total:
            note += f", showing {offset + 1}-{offset + len(chunk)}"
        return ToolResult(note + "\n" + trunc(body))

    def write_file(path: str, content: str) -> ToolResult:
        p = resolve_path(path, cwd)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except OSError as e:
            return ToolResult(f"Cannot write {p}: {e}", is_error=True)
        return ToolResult(f"Wrote {len(content)} chars to {p}")

    def edit_file(
        path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> ToolResult:
        p = resolve_path(path, cwd)
        if not p.exists():
            return ToolResult(f"File not found: {p}", is_error=True)
        text = p.read_text(encoding="utf-8", errors="replace")
        count = text.count(old_string)
        if count == 0:
            return ToolResult("old_string not found in file", is_error=True)
        if count > 1 and not replace_all:
            return ToolResult(
                f"old_string occurs {count} times; pass replace_all=true or add context",
                is_error=True,
            )
        new_text = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
        p.write_text(new_text, encoding="utf-8")
        return ToolResult(f"Edited {p} ({count if replace_all else 1} replacement(s))")

    def ls(path: str = ".") -> ToolResult:
        p = resolve_path(path, cwd)
        if not p.is_dir():
            return ToolResult(f"Not a directory: {p}", is_error=True)
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name))
        lines = [
            ("d " if e.is_dir() else "  ") + e.name + ("/" if e.is_dir() else "")
            for e in entries[:500]
        ]
        return ToolResult("\n".join(lines) or "(empty)")

    def glob_files(pattern: str, path: str = ".") -> ToolResult:
        root = resolve_path(path, cwd)
        try:
            matches = sorted(root.glob(pattern))
        except (ValueError, re.error) as e:
            return ToolResult(f"Bad pattern: {e}", is_error=True)
        rel = [str(m.relative_to(root)) if m.is_relative_to(root) else str(m) for m in matches[:500]]
        return ToolResult("\n".join(rel) or "No matches")

    def grep(pattern: str, path: str = ".", glob: str | None = None, ignore_case: bool = False) -> ToolResult:
        root = resolve_path(path, cwd)
        if shutil.which("rg"):
            cmd = ["rg", "--line-number", "--max-count", "200", "--color", "never"]
            if ignore_case:
                cmd.append("-i")
            if glob:
                cmd += ["-g", glob]
            cmd += ["--", pattern, str(root)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode not in (0, 1):
                return ToolResult(proc.stderr.strip() or "rg failed", is_error=True)
            return ToolResult(trunc(proc.stdout.strip() or "No matches"))

        try:
            rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error as e:
            return ToolResult(f"Bad regex: {e}", is_error=True)
        hits: list[str] = []
        files = [root] if root.is_file() else (p for p in root.rglob("*") if p.is_file())
        for f in files:
            if glob and not f.match(glob):
                continue
            try:
                for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{f}:{n}:{line.strip()[:200]}")
                        if len(hits) >= 200:
                            return ToolResult(trunc("\n".join(hits)))
            except OSError:
                continue
        return ToolResult(trunc("\n".join(hits) or "No matches"))

    return [
        Tool(
            name="read_file",
            description="Read a file with line numbers. offset/limit paginate.",
            parameters=obj(
                {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "default": 0},
                    "limit": {"type": "integer", "default": MAX_LINES},
                },
                ["path"],
            ),
            func=read_file,
            summarize=lambda a: a.get("path", ""),
        ),
        Tool(
            name="write_file",
            description="Write (create or overwrite) a file. Creates parent dirs.",
            parameters=obj(
                {"path": {"type": "string"}, "content": {"type": "string"}},
                ["path", "content"],
            ),
            func=write_file,
            needs_approval=True,
            summarize=lambda a: f"write {a.get('path', '')} ({len(a.get('content', ''))} chars)",
        ),
        Tool(
            name="edit_file",
            description="Exact string replacement in a file. old_string must be unique unless replace_all.",
            parameters=obj(
                {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                    "replace_all": {"type": "boolean", "default": False},
                },
                ["path", "old_string", "new_string"],
            ),
            func=edit_file,
            needs_approval=True,
            summarize=lambda a: f"edit {a.get('path', '')}",
        ),
        Tool(
            name="ls",
            description="List directory contents.",
            parameters=obj({"path": {"type": "string", "default": "."}}, []),
            func=ls,
            summarize=lambda a: a.get("path", "."),
        ),
        Tool(
            name="glob",
            description="Find files by glob pattern relative to a directory.",
            parameters=obj(
                {"pattern": {"type": "string"}, "path": {"type": "string", "default": "."}},
                ["pattern"],
            ),
            func=glob_files,
            summarize=lambda a: a.get("pattern", ""),
        ),
        Tool(
            name="grep",
            description="Regex search in files (ripgrep when available, pure-Python fallback).",
            parameters=obj(
                {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "glob": {"type": "string"},
                    "ignore_case": {"type": "boolean", "default": False},
                },
                ["pattern"],
            ),
            func=grep,
            summarize=lambda a: f"/{a.get('pattern', '')}/ in {a.get('path', '.')}",
        ),
    ]
