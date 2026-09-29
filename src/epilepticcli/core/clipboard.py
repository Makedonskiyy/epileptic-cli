"""Clipboard access utility for EpilepticCLI."""

from __future__ import annotations

import subprocess
import sys


def get_clipboard_text() -> str | None:
    """Read text from system clipboard across Windows, Linux, and macOS."""
    if sys.platform == "win32":
        # Native Win32 API via ctypes (zero dependencies, fast, reliable)
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.GetClipboardData.restype = wintypes.HANDLE
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = wintypes.LPVOID
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            user32.CloseClipboard.argtypes = []

            if user32.OpenClipboard(None):
                try:
                    CF_UNICODETEXT = 13
                    handle = user32.GetClipboardData(CF_UNICODETEXT)
                    if handle:
                        ptr = kernel32.GlobalLock(handle)
                        if ptr:
                            try:
                                return str(ctypes.c_wchar_p(ptr).value or "")
                            finally:
                                kernel32.GlobalUnlock(handle)
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

        # Fallback via PowerShell on Windows
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
            )
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass

    # Linux / macOS fallback tools
    for cmd in (["pbpaste"], ["wl-paste"], ["xclip", "-selection", "clipboard", "-o"]):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            continue

    return None
