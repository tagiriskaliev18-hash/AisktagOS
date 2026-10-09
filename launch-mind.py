#!/usr/bin/env python3
"""Windows-лаунчер Mind IDE — запускает aisktag-mind.py с правильными путями.

Этот файл лежит в корне проекта и патчит sys.path так, чтобы импорты
aisktag_ai и aisktag_theme работали как на Linux, так и на Windows.
"""
import sys
import os
from pathlib import Path

# ── Корень проекта (папка, где лежит этот файл) ──────────────────────────────
PROJECT = Path(__file__).resolve().parent

# ── Добавляем overlay/usr/lib/aisktagos в путь поиска модулей ────────────────
LIB_DIR = PROJECT / "overlay" / "usr" / "lib" / "aisktagos"
sys.path.insert(0, str(LIB_DIR))

# ── Переменные окружения: токены дизайна и каталог моделей ───────────────────
os.environ.setdefault(
    "AISKTAG_TOKENS",
    str(PROJECT / "overlay" / "usr" / "share" / "aisktagos" / "design" / "tokens.json"),
)
os.environ.setdefault(
    "AISKTAG_CATALOG",
    str(PROJECT / "overlay" / "usr" / "share" / "aisktagos" / "ai" / "models.json"),
)

# ── Для Windows: рендеринг без Wayland/X11 ───────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

# ── Запускаем Mind ────────────────────────────────────────────────────────────
mind_script = LIB_DIR / "aisktag-mind.py"

# Патчим внутри mind.py: заменяем хардкоженный Linux-путь на наш
with open(mind_script, encoding="utf-8") as f:
    src = f.read()

# Выполняем скрипт в текущем пространстве имён, чтобы sys.path уже был нашим
exec(compile(src, str(mind_script), "exec"), {"__file__": str(mind_script), "__name__": "__main__"})
