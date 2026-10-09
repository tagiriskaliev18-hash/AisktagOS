"""Доступ к системному буферу обмена без зависимостей.

Linux: wl-clipboard (Wayland), xclip или xsel (X11). Windows: PowerShell.
macOS: pbcopy/pbpaste. Если ничего нет — буфер живёт в памяти процесса,
чтобы MindLink и тесты работали и без графической сессии.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from .paths import IS_MAC, IS_WINDOWS

_memory = {"text": ""}


def _commands() -> tuple[list[str], list[str]] | None:
    if os.environ.get("MINDKIT_CLIPBOARD") == "memory":
        return None
    if IS_WINDOWS:
        ps = ["powershell", "-NoProfile", "-Command"]
        return ps + ["Get-Clipboard -Raw"], ps + ["$input | Set-Clipboard"]
    if IS_MAC:
        return ["pbpaste"], ["pbcopy"]
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste") and shutil.which("wl-copy"):
        return ["wl-paste", "--no-newline"], ["wl-copy"]
    if os.environ.get("DISPLAY"):
        if shutil.which("xclip"):
            return ["xclip", "-selection", "clipboard", "-o"], ["xclip", "-selection", "clipboard"]
        if shutil.which("xsel"):
            return ["xsel", "--clipboard", "--output"], ["xsel", "--clipboard", "--input"]
    return None


def backend() -> str:
    cmds = _commands()
    return cmds[0][0] if cmds else "memory"


def get() -> str:
    cmds = _commands()
    if not cmds:
        return _memory["text"]
    try:
        out = subprocess.run(cmds[0], capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return _memory["text"]
    text = out.stdout.decode("utf-8", "replace")
    if IS_WINDOWS:
        text = text.removesuffix("\r\n")
    return text


def set(text: str) -> None:  # noqa: A001
    _memory["text"] = text
    cmds = _commands()
    if not cmds:
        return
    try:
        subprocess.run(cmds[1], input=text.encode("utf-8"), timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass
