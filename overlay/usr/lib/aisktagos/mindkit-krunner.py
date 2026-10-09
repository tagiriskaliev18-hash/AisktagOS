#!/usr/bin/env python3
"""Mind Search в KRunner (Meta+Space): приложения MindTagSystem, быстрые команды,
входящие Handoff и файлы проектов прямо в поиске AIsktagOS, как в Spotlight.

D-Bus-плагин KRunner (интерфейс org.kde.krunner1). Запускается сам по первому
запросу через /usr/share/dbus-1/services/org.mindtagsystem.search.service.
"""
import shlex
import subprocess
import sys
import time

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from mindkit import search

IFACE = "org.kde.krunner1"
# Программы KRunner и так находит сам; ключи из связки в поиск не выводим
KINDS = {"app", "shortcut", "history", "file"}
ICONS = {"app": "aisktag-mind", "shortcut": "system-run", "handoff": "kdeconnect",
         "notification": "preferences-desktop-notification", "file": "text-x-generic",
         "text": "text-x-script"}
FILE_TTL = 120  # секунд: список файлов проектов кэшируется
MINDKIT = [sys.executable, "-m", "mindkit"]


def terminal(*cmd: str) -> None:
    """Команды, которым нужен вывод (установка из Mind Store), идут в kitty."""
    line = " ".join(shlex.quote(c) for c in cmd)
    subprocess.Popen(["kitty", "--hold", "sh", "-c", line])


class Runner(dbus.service.Object):
    def __init__(self):
        # Имя шины передаётся в Object: так на него есть ссылка и его не освободит сборщик мусора
        name = dbus.service.BusName("org.mindtagsystem.search", dbus.SessionBus())
        super().__init__(name, "/runner")
        self.matches: dict[str, dict] = {}
        self.files: tuple[float, list] = (0.0, [])

    def _file_roots(self):
        # Обход папок дорогой: при частых нажатиях клавиш кэшируем результат
        now = time.time()
        if now - self.files[0] > FILE_TTL:
            self.files = (now, list(search.iter_files()))
        return self.files[1]

    @dbus.service.method(IFACE, in_signature="s", out_signature="a(sssida{sv})")
    def Match(self, query: str):
        results = search.search(query, limit=12, kinds=KINDS - {"file"})
        for path in self._file_roots():
            s = search.score(query, path.name)
            if s >= 50:
                results.append({"kind": "file", "title": path.name, "subtitle": str(path.parent),
                                "action": {"open": str(path)}, "score": s * 0.9})
        results.sort(key=lambda r: -r["score"])
        out = []
        self.matches.clear()
        for i, r in enumerate(results[:12]):
            mid = f"m{i}"
            self.matches[mid] = r
            props = {"subtext": r["subtitle"][:200],
                     # Кнопка «Установить» только у приложений; пустой список скрывает действия
                     "actions": dbus.Array(["install"] if r["kind"] == "app" else [], signature="s")}
            if r["kind"] == "file":
                props["urls"] = dbus.Array(["file://" + r["action"]["open"]], signature="s")
            # Тип 100 — точное совпадение, 70 — возможное (KRunner::QueryMatch::CategoryRelevance)
            out.append((mid, r["title"], ICONS.get(r["kind"], "search"), 100 if r["score"] >= 80 else 70,
                        min(r["score"] / 100.0, 1.0), props))
        return out

    @dbus.service.method(IFACE, out_signature="a(sss)")
    def Actions(self):
        return [("install", "Установить из Mind Store", "download")]

    @dbus.service.method(IFACE, in_signature="ss")
    def Run(self, match_id: str, action_id: str):
        r = self.matches.get(match_id)
        if not r:
            return
        act = r["action"]
        if "store" in act:
            if action_id == "install" or not r["subtitle"].endswith("установлено"):
                terminal(*MINDKIT, "store", "install", act["store"])
            else:
                subprocess.Popen(MINDKIT + ["store", "run", act["store"]])
        elif "shortcut" in act:
            subprocess.Popen(MINDKIT + ["shortcuts", "run", act["shortcut"]])
        elif "resume" in act:
            subprocess.Popen(MINDKIT + ["handoff", "resume", str(act["resume"])])
        elif "open" in act:
            subprocess.Popen(["xdg-open", act["open"]])


def main() -> None:
    DBusGMainLoop(set_as_default=True)
    Runner()
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
