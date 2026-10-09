#!/usr/bin/env python3
"""Снимки интерфейса PyQt-приложений AIsktagOS без графической сессии (Qt offscreen) — для проверки дизайна.

    python3 tools/shot-ui.py mind   out.png      # окно Mind с заглушкой модели (tools/mock-llm.py)
    python3 tools/shot-ui.py center out.png [страница]   # Центр AIsktagOS: welcome|drivers|ai|dev|system

Нужны PyQt6 и (для Mind) запущенный `python3 tools/mock-llm.py 16573`. Шрифта Inter на хосте может не быть,
поэтому размеры текста чуть отличаются от настоящей системы; цвета и компоновка — те же.
"""
import importlib.util
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":      # у offscreen-плагина на Windows нет шрифтов — берём системные
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
LIB = Path(__file__).resolve().parent.parent / "overlay/usr/lib/aisktagos"
sys.path.insert(0, str(LIB))
os.environ.setdefault("AI_BASE_URL", "http://127.0.0.1:16573/v1")
SHARE = Path(__file__).resolve().parent.parent / "overlay/usr/share/aisktagos"
os.environ.setdefault("AISKTAG_CATALOG", str(SHARE / "ai/models.json"))
os.environ.setdefault("AISKTAG_TOKENS", str(SHARE / "design/tokens.json"))

from PyQt6.QtWidgets import QApplication  # noqa: E402


def load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), LIB / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pump(app, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def main() -> None:
    kind, out = sys.argv[1], sys.argv[2]
    app = QApplication(sys.argv)
    if kind == "mind":
        mod = load("aisktag-mind")
        app.setStyleSheet(mod.QSS)
        win = mod.Mind()
        win.show()
        pump(app, 0.5)
        win.grab().save(out.replace(".png", "-empty.png"))
        win.input.setPlainText("Как найти самые большие файлы в папке?")
        win.add_attachment("error.log", "Permission denied: /etc/shadow")
        win.send()
        pump(app, 3.0)
        win.grab().save(out)
    elif kind == "center":
        mod = load("aisktag-center")
        app.setStyleSheet(mod.STYLE)
        win = mod.Center(sys.argv[3] if len(sys.argv) > 3 else "welcome")
        win.show()
        pump(app, 1.0)
        win.grab().save(out)
    print("сохранено:", out)


if __name__ == "__main__":
    main()
