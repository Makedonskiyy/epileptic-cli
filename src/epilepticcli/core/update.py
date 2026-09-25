"""Update checking and self-update for the packaged exe build.

- `check_for_update` hits the GitHub Releases API (cached 24h) so the REPL
  can hint when a newer version exists.
- `self_update` replaces the running PyInstaller exe: downloads the new
  binary next to the current one, then launches a tiny .cmd that swaps it
  after this process exits and relaunches the app.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from epilepticcli import __version__
from epilepticcli.config import APP_DIR

REPO = "Makedonskiyy/epileptic-cli"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CACHE_FILE = APP_DIR / "update_check.json"
CACHE_TTL = 24 * 3600
EXE_ASSET = "epileptic.exe"


@dataclass
class UpdateInfo:
    tag: str
    url: str
    newer: bool


def _parse_ver(tag: str) -> tuple[int, ...]:
    parts = []
    for piece in tag.lstrip("vV").split("."):
        digits = "".join(c for c in piece if c.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def latest_release(timeout: float = 4.0) -> UpdateInfo | None:
    try:
        resp = httpx.get(
            API_URL, timeout=timeout,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "EpilepticCLI"},
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return None
    tag = str(data.get("tag_name") or "")
    if not tag:
        return None
    return UpdateInfo(
        tag=tag,
        url=data.get("html_url", ""),
        newer=_parse_ver(tag) > _parse_ver(__version__),
    )


def cached_latest() -> UpdateInfo | None:
    """Latest release info, cached on disk for CACHE_TTL seconds."""
    try:
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - data.get("checked_at", 0) < CACHE_TTL:
                return UpdateInfo(
                    tag=data["tag"], url=data.get("url", ""),
                    newer=_parse_ver(data["tag"]) > _parse_ver(__version__),
                )
    except (OSError, ValueError, KeyError):
        pass
    info = latest_release()
    if info:
        with contextlib.suppress(OSError):
            CACHE_FILE.write_text(
                json.dumps({"tag": info.tag, "url": info.url, "checked_at": time.time()}),
                encoding="utf-8",
            )
    return info


def check_async(on_result) -> threading.Thread:
    t = threading.Thread(target=lambda: on_result(cached_latest()), daemon=True)
    t.start()
    return t


def download_asset(url: str, dest: Path, timeout: float = 300.0) -> None:
    with httpx.stream("GET", url, follow_redirects=True, timeout=timeout,
                      headers={"User-Agent": "EpilepticCLI"}) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_bytes(1 << 16):
                f.write(chunk)


def _find_exe_asset(info: UpdateInfo) -> str | None:
    try:
        resp = httpx.get(API_URL, timeout=10,
                         headers={"Accept": "application/vnd.github+json"})
        for a in resp.json().get("assets", []):
            if a.get("name") == EXE_ASSET:
                return a.get("browser_download_url")
    except (httpx.HTTPError, ValueError):
        pass
    return None


def self_update() -> str:
    """Returns a human-readable status message."""
    info = latest_release(timeout=10)
    if info is None:
        return "could not reach the releases API"
    if not info.newer:
        return f"already on latest version ({__version__})"

    if not _is_frozen():
        # Source/pip install: reinstall from the repo
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U",
                 f"epilepticcli @ git+https://github.com/{REPO}@main"],
                capture_output=True, text=True, timeout=600,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"update failed: {e}"
        if proc.returncode == 0:
            return f"updated to {info.tag} - restart the CLI"
        return f"pip update failed:\n{(proc.stderr or proc.stdout)[-800:]}"

    # Frozen exe: swap binary after this process exits
    asset_url = _find_exe_asset(info)
    if not asset_url:
        return f"release {info.tag} has no {EXE_ASSET} asset"
    exe_path = Path(sys.executable)
    new_path = exe_path.with_suffix(".new.exe")
    try:
        download_asset(asset_url, new_path)
    except (httpx.HTTPError, OSError) as e:
        return f"download failed: {e}"

    if os.name == "nt":
        script = Path(tempfile.gettempdir()) / "epileptic_update.cmd"
        script.write_text(
            "@echo off\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            f'move /y "{new_path}" "{exe_path}"\r\n'
            f'start "" "{exe_path}"\r\n'
            'del "%~f0"\r\n',
            encoding="utf-8",
        )
        subprocess.Popen(
            ["cmd", "/c", str(script)],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            close_fds=True,
        )
        return f"downloaded {info.tag} - restarting to apply update"

    # POSIX frozen build (future)
    try:
        new_path.chmod(0o755)
        backup = exe_path.with_suffix(".old")
        exe_path.replace(backup)
        new_path.replace(exe_path)
        return f"updated to {info.tag} - restart the CLI"
    except OSError as e:
        return f"could not replace binary: {e}"
