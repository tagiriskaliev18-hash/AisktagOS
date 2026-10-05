#!/usr/bin/env python3
"""Дизайн-система AIsktagOS «Aurora»: единый источник правды для цветов, скруглений и шрифтов.

Логика цвета (один смысл — один цвет):
- синий  (accent)  — система: выделение, кнопки «Далее/Установить», активное окно;
- бирюзовый (focus) — внимание: фокус, наведение, индикаторы;
- фиолетовый (ai)   — всё, что делает нейросеть (кнопка ИИ, пузыри ассистента, статус модели).
Логотип — градиент «фиолетовый → бирюзовый»: нейросеть, превращающаяся в систему.

Запуск:  python3 assets/tokens.py          — записать overlay/usr/share/aisktagos/design/tokens.json
         python3 assets/tokens.py --check  — проверить контраст WCAG AA для пар «текст/фон»
Генераторы графики и PyQt-приложения (Центр, ИИ-ассистент) берут цвета отсюда, а не из своих констант.
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "overlay/usr/share/aisktagos/design/tokens.json"

COLORS = {
    # Фоны (от самого тёмного к самому светлому)
    "bg0": "#070b16",        # терминал, код, глубокие впадины
    "bg1": "#0b1020",        # окна и приложения
    "bg2": "#111a33",        # панели, боковые списки
    "surface": "#16203d",    # карточки
    "surface2": "#1e2a50",   # карточки при наведении, поля ввода
    # Текст
    "text": "#eef3ff",
    "text2": "#b8c2e0",      # второстепенный
    "muted": "#8f9abf",      # подписи и подсказки
    # Акценты
    "accent": "#3d7bff",     # системный синий (AccentColor KDE, активное окно)
    "accentStrong": "#2a5be0",  # заливка кнопок: белый текст держит контраст AA
    "focus": "#22e4ff",      # фокус/наведение/индикаторы
    "ai": "#8b5cf6",         # ИИ: заливки и рамки
    "aiText": "#b79cff",     # ИИ: текст на тёмном фоне
    # Состояния
    "ok": "#2fd27a",
    "warn": "#febc2e",
    "danger": "#ff5f57",
}

# Пары (текст, фон, минимальный контраст, где используется)
PAIRS = [
    ("text", "bg1", 4.5, "основной текст окна"),
    ("text", "surface", 4.5, "текст в карточке"),
    ("text", "surface2", 4.5, "текст в поле ввода"),
    ("text2", "bg1", 4.5, "второстепенный текст"),
    ("text2", "bg2", 4.5, "пункты боковой панели"),
    ("muted", "bg1", 4.5, "подписи и подсказки"),
    ("muted", "bg2", 4.5, "подписи в боковой панели"),
    ("text", "accentStrong", 4.5, "текст на кнопке"),
    ("accent", "bg1", 4.5, "ссылки и активные подписи"),
    ("focus", "bg1", 4.5, "индикаторы и фокус"),
    ("aiText", "bg1", 4.5, "текст ИИ-ассистента"),
    ("aiText", "surface", 4.5, "текст ИИ в карточке"),
    ("ok", "bg1", 4.5, "статус «в порядке»"),
    ("warn", "bg1", 4.5, "статус «внимание»"),
    ("danger", "bg1", 4.5, "статус «ошибка»"),
    ("accent", "bg0", 3.0, "значки на панели задач (не текст, достаточно 3:1)"),
]

SCALE = {
    "radius": {"control": 8, "card": 14, "window": 14, "pill": 999},
    "space": [4, 8, 12, 16, 24, 32],
    "font": {"ui": "Inter", "mono": "JetBrains Mono", "size": {"small": 9, "body": 10.5, "h2": 13.5, "h1": 22}},
}


def luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def rgb(name: str) -> tuple[int, int, int]:
    h = COLORS[name]
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def check() -> int:
    bad = 0
    print(f"{'пара':<24}{'контраст':>9}  нужно  где применяется")
    for fg, bg, need, where in PAIRS:
        c = contrast(COLORS[fg], COLORS[bg])
        ok = c >= need
        bad += not ok
        print(f"{fg + ' на ' + bg:<24}{c:>8.2f}  {need:>4}   {'✔' if ok else '✘'} {where}")
    print("Все пары проходят WCAG AA." if not bad else f"Не проходят: {bad}")
    return 1 if bad else 0


def write() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {"name": "Aurora", "colors": COLORS, **SCALE}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Токены записаны:", OUT)


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    write()
    sys.exit(check())
