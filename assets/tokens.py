#!/usr/bin/env python3
"""Дизайн-система AIsktagOS «Aurora» — Apple-like редакция.

Философия дизайна:
  • Чистота — каждый элемент дышит. Много воздуха, мало шума.
  • Контраст — чёрное на белом (тёмный режим: белое на чёрном). Никаких полутонов без смысла.
  • Характер — один фирменный градиент на весь бренд (фиолетовый → циан «Aurora»).
  • Смелость — большие шрифты, крупные скругления, уверенные тени.
  • Система — один источник правды; все приложения OS используют только эти токены.

Каждый модуль / приложение в AIsktagOS получает свою акцентную пару (см. APP_ACCENTS).

Запуск:  python3 assets/tokens.py          — записать tokens.json
         python3 assets/tokens.py --check  — WCAG AA проверка контраста
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "overlay/usr/share/aisktagos/design/tokens.json"

# ---------------------------------------------------------------------------
# Цвета — Aurora Apple-like
# ---------------------------------------------------------------------------
COLORS = {
    # ── Фоны ────────────────────────────────────────────────────────────────
    "bg0":       "#050508",   # абсолютный чёрный — терминал, код, подложка
    "bg1":       "#09090f",   # главный фон окна (macOS-уровень тёмного)
    "bg2":       "#0f0f1a",   # боковые панели, дроверы
    "surface":   "#141421",   # карточки, диалоги
    "surface2":  "#1c1c2e",   # поля ввода, hover-state карточек
    "glass":     "#ffffff0d", # frosted-glass оверлеи (8% белого)

    # ── Текст ───────────────────────────────────────────────────────────────
    "text":      "#f5f5f7",   # главный (Apple SF-white)
    "text2":     "#a1a1b5",   # второстепенный
    "muted":     "#636378",   # подписи, placeholder

    # ── Акценты системы ─────────────────────────────────────────────────────
    "accent":       "#6e56cf", # SystemViolet — основной бренд
    "accentHover":  "#7c66df", # hover кнопок
    "accentStrong": "#5a45b5", # pressed / заливка
    "accentGlow":   "#6e56cf40", # свечение (25% alpha)

    # ── Aurora-градиент (логотип + ИИ) ──────────────────────────────────────
    "ai":        "#9B5DE5",   # фиолетовый конец
    "aiMid":     "#5b8dee",   # синяя середина
    "aiCyan":    "#00F5FF",   # циановый конец
    "aiText":    "#c4b5fd",   # текст ИИ на тёмном фоне

    # ── Фокус / интерактив ──────────────────────────────────────────────────
    "focus":     "#00F5FF",   # ring-цвет фокуса
    "focusSoft": "#00F5FF28", # мягкий фон фокуса

    # ── Семантические ───────────────────────────────────────────────────────
    "ok":        "#30d158",   # Apple-green
    "warn":      "#ffd60a",   # Apple-yellow
    "danger":    "#ff453a",   # Apple-red
    "info":      "#0a84ff",   # Apple-blue
}

# Акцентные пары для каждого приложения ОС (фон кнопки, текст)
APP_ACCENTS = {
    "mind":    ("#9B5DE5", "#f5f5f7"),   # фиолетовый — ИИ
    "center":  ("#0a84ff", "#f5f5f7"),   # синий — система
    "terminal":("#00F5FF", "#050508"),   # циан — терминал
    "code":    ("#30d158", "#050508"),   # зелёный — редактор
    "design":  ("#ff375f", "#f5f5f7"),   # маджента — дизайн
}

# Контрастные пары для WCAG AA (текст, фон, мин. контраст, описание)
PAIRS = [
    ("text",    "bg1",      4.5, "основной текст"),
    ("text",    "surface",  4.5, "текст в карточке"),
    ("text",    "surface2", 4.5, "текст в поле ввода"),
    ("text2",   "bg1",      4.5, "второстепенный текст"),
    ("text2",   "bg2",      4.5, "пункты боковой панели"),
    ("muted",   "bg1",      3.0, "подписи (крупный шрифт ≥ 18pt)"),
    ("text",    "accentStrong", 4.5, "текст на кнопке"),
    ("aiText",  "bg1",      4.5, "текст ИИ"),
    ("aiText",  "surface",  4.5, "текст ИИ в карточке"),
    ("ok",      "bg1",      3.0, "статус OK"),
    ("warn",    "bg1",      3.0, "статус warn"),
    ("danger",  "bg1",      3.0, "статус danger"),
]

# Типографика и метрика
SCALE = {
    "radius": {
        "xs":      6,    # чипы, теги
        "sm":      10,   # кнопки, поля
        "md":      16,   # карточки
        "lg":      24,   # окна, диалоги
        "xl":      32,   # hero-блоки
        "full":    999,  # pill-кнопки
    },
    "space":  [4, 8, 12, 16, 20, 24, 32, 48, 64],
    "shadow": {
        "sm":  "0 1px 3px rgba(0,0,0,0.5), 0 1px 2px rgba(0,0,0,0.8)",
        "md":  "0 4px 16px rgba(0,0,0,0.6)",
        "lg":  "0 12px 40px rgba(0,0,0,0.7)",
        "glow":"0 0 24px rgba(110,86,207,0.5)",
    },
    "font": {
        "ui":   "SF Pro Display, Inter, system-ui, sans-serif",
        "mono": "SF Mono, JetBrains Mono, monospace",
        "size": {
            "caption": 8,
            "small":   9.5,
            "body":    11,
            "lead":    13,
            "h3":      16,
            "h2":      22,
            "h1":      34,
            "display": 56,
        },
        "weight": {"regular": 400, "medium": 500, "semibold": 600, "bold": 700},
        "tracking": {"tight": -0.5, "normal": 0, "wide": 0.5, "wider": 1.0},
    },
    "transition": "all 0.18s cubic-bezier(0.25, 0.46, 0.45, 0.94)",
}


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

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
    print(f"{'пара':<26}{'контраст':>9}  нужно  где применяется")
    for fg, bg, need, where in PAIRS:
        c = contrast(COLORS[fg], COLORS[bg])
        ok = c >= need
        bad += not ok
        mark = "✔" if ok else "✘"
        print(f"{fg + ' на ' + bg:<26}{c:>8.2f}  {need:>4}   {mark} {where}")
    print("Все пары проходят WCAG AA." if not bad else f"Не проходят: {bad}")
    return 1 if bad else 0


def write() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name":        "Aurora",
        "version":     "2.0",
        "theme":       "apple-like",
        "colors":      COLORS,
        "app_accents": APP_ACCENTS,
        **SCALE,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Токены записаны:", OUT)


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    write()
    sys.exit(check())
