"""Где MindKit хранит настройки и данные на Linux, Windows и macOS."""

from __future__ import annotations

import os
import sys
from pathlib import Path

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"


def config_dir() -> Path:
    """Папка настроек экосистемы: ~/.config/mindtagsystem или %APPDATA%\\MindTagSystem."""
    if os.environ.get("MINDKIT_HOME"):
        return Path(os.environ["MINDKIT_HOME"])
    if IS_WINDOWS and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "MindTagSystem"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "mindtagsystem"


def data_dir() -> Path:
    """Папка данных: история уведомлений, входящие Handoff, кэш каталога."""
    if os.environ.get("MINDKIT_HOME"):
        return Path(os.environ["MINDKIT_HOME"]) / "data"
    if IS_WINDOWS and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "MindTagSystem"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "mindtagsystem"


def downloads_dir() -> Path:
    """Куда MindDrop (аналог AirDrop) кладёт принятые файлы."""
    if os.environ.get("MINDKIT_HOME"):
        return Path(os.environ["MINDKIT_HOME"]) / "MindDrop"
    return Path.home() / "Downloads" / "MindDrop"


def private_write(path: Path, text: str) -> None:
    """Записывает файл, доступный только владельцу (для секретов)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass
