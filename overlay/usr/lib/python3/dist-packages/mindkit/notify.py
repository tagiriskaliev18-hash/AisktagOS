"""Центр уведомлений: показывает уведомление и хранит историю.

Уведомления от любого проекта экосистемы и с любого устройства
(через MindLink) попадают в одну историю ``<data_dir>/notifications.jsonl``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from .paths import IS_MAC, IS_WINDOWS, data_dir

HISTORY_LIMIT = 500


def _history_path():
    return data_dir() / "notifications.jsonl"


def _show(title: str, body: str, app: str) -> bool:
    """Системное уведомление. False — показать некуда (сервер, тесты)."""
    if os.environ.get("MINDKIT_NOTIFY") == "off":
        return False
    try:
        if IS_WINDOWS:
            # Встроенный в Windows способ без сторонних модулей
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;"
                "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
                "$x=$t.GetElementsByTagName('text');$x.Item(0).AppendChild($t.CreateTextNode($env:MK_TITLE))>$null;"
                "$x.Item(1).AppendChild($t.CreateTextNode($env:MK_BODY))>$null;"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:MK_APP).Show("
                "[Windows.UI.Notifications.ToastNotification]::new($t))"
            )
            env = dict(os.environ, MK_TITLE=title, MK_BODY=body, MK_APP=app)
            subprocess.Popen(["powershell", "-NoProfile", "-Command", script], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if IS_MAC:
            subprocess.Popen(["osascript", "-e", "on run argv\ndisplay notification (item 2 of argv) "
                              "with title (item 1 of argv)\nend run", title, body])
            return True
        if shutil.which("notify-send") and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            subprocess.Popen(["notify-send", "-a", app, "-i", "aisktag-mind", title, body],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except OSError:
        pass
    return False


def send(title: str, body: str = "", app: str = "MindTagSystem", source: str = "", show: bool = True) -> dict:
    item = {"time": time.time(), "app": app, "title": title, "body": body, "source": source}
    if show:
        item["shown"] = _show(title, body, app)
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    _trim(path)
    return item


def _trim(path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) > HISTORY_LIMIT * 2:
        path.write_text("\n".join(lines[-HISTORY_LIMIT:]) + "\n", encoding="utf-8")


def history(limit: int = 20) -> list[dict]:
    path = _history_path()
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def clear() -> None:
    path = _history_path()
    if path.exists():
        path.unlink()
