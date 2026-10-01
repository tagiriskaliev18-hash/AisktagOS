#!/usr/bin/env python3
"""Стиль Plasma «AIsktagOS Glass»: стеклянные панели для строки меню и плавающего дока.

Генерирует overlay/usr/share/plasma/desktoptheme/AIsktagOS/:
- widgets/panel-background.svg      — без размытия (непрозрачнее, чтобы текст читался);
- translucent/widgets/...           — когда в KWin работает blur: стекло с непрозрачностью 0.75;
- opaque/widgets/...                — без композитинга;
- widgets/line.svg                  — разделители в доке: тонкая линия, гаснущая к краям;
- metadata.json / metadata.desktop / plasmarc — описание темы, контраст и размытие.

Всё, чего здесь нет (кнопки, подсказки, календарь…), берётся из breeze-dark (FallbackTheme).
Картинки чисто векторные; у каждой части рамки свой id, как требует Plasma FrameSvg.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "overlay/usr/share/plasma/desktoptheme/AIsktagOS"

R = 14        # радиус скругления плавающего дока
MID = 10      # размер растягиваемых частей
SH = 22       # размер тени вокруг панели
MARGIN = 4    # внутренние отступы содержимого (hint-*-margin), не зависят от радиуса


def frame(prefix: str, fill: str, opacity: float, rim: str, rim_op: float,
          shine_op: float, ox: float, oy: float) -> str:
    """9 частей скруглённой рамки. Обводка смещена внутрь на 0.5, чтобы не выходить за границы части."""
    p = f"{prefix}-" if prefix else ""
    f = f'fill="{fill}" fill-opacity="{opacity}"'
    s = f'fill="none" stroke="{rim}" stroke-opacity="{rim_op}" stroke-width="1"'
    hl = f'fill="none" stroke="#ffffff" stroke-opacity="{shine_op}" stroke-width="1"'
    a = R - 0.5
    x1, x2 = ox + R, ox + R + MID          # левая граница середины и правой колонки
    y1, y2 = oy + R, oy + R + MID
    parts = {
        "topleft": (ox, oy,
                    f'<path d="M{ox},{oy + R}A{R},{R} 0 0 1 {ox + R},{oy}V{oy + R}Z" {f}/>'
                    f'<path d="M{ox + 0.5},{oy + R}A{a},{a} 0 0 1 {ox + R},{oy + 0.5}" {s}/>'
                    f'<path d="M{ox + 1.5},{oy + R}A{a - 1},{a - 1} 0 0 1 {ox + R},{oy + 1.5}" {hl}/>'),
        "top": (x1, oy,
                f'<rect x="{x1}" y="{oy}" width="{MID}" height="{R}" {f}/>'
                f'<path d="M{x1},{oy + 0.5}H{x2}" {s}/><path d="M{x1},{oy + 1.5}H{x2}" {hl}/>'),
        "topright": (x2, oy,
                     f'<path d="M{x2},{oy}A{R},{R} 0 0 1 {x2 + R},{oy + R}H{x2}Z" {f}/>'
                     f'<path d="M{x2},{oy + 0.5}A{a},{a} 0 0 1 {x2 + R - 0.5},{oy + R}" {s}/>'
                     f'<path d="M{x2},{oy + 1.5}A{a - 1},{a - 1} 0 0 1 {x2 + R - 1.5},{oy + R}" {hl}/>'),
        "left": (ox, y1,
                 f'<rect x="{ox}" y="{y1}" width="{R}" height="{MID}" {f}/>'
                 f'<path d="M{ox + 0.5},{y1}V{y2}" {s}/>'),
        "center": (x1, y1, f'<rect x="{x1}" y="{y1}" width="{MID}" height="{MID}" {f}/>'),
        "right": (x2, y1,
                  f'<rect x="{x2}" y="{y1}" width="{R}" height="{MID}" {f}/>'
                  f'<path d="M{x2 + R - 0.5},{y1}V{y2}" {s}/>'),
        "bottomleft": (ox, y2,
                       f'<path d="M{ox},{y2}H{ox + R}V{y2 + R}A{R},{R} 0 0 1 {ox},{y2}Z" {f}/>'
                       f'<path d="M{ox + 0.5},{y2}A{a},{a} 0 0 0 {ox + R},{y2 + R - 0.5}" {s}/>'),
        "bottom": (x1, y2,
                   f'<rect x="{x1}" y="{y2}" width="{MID}" height="{R}" {f}/>'
                   f'<path d="M{x1},{y2 + R - 0.5}H{x2}" {s}/>'),
        "bottomright": (x2, y2,
                        f'<path d="M{x2},{y2}H{x2 + R}A{R},{R} 0 0 1 {x2},{y2 + R}Z" {f}/>'
                        f'<path d="M{x2 + R - 0.5},{y2}A{a},{a} 0 0 1 {x2},{y2 + R - 0.5}" {s}/>'),
    }
    return "\n".join(f'<g id="{p}{name}">{body}</g>' for name, (_x, _y, body) in parts.items())


def shadow(ox: float, oy: float) -> str:
    """Мягкая тень вокруг панели: углы — радиальные градиенты, стороны — линейные."""
    k = SH
    out = []
    corners = {
        "topleft": (ox, oy, ox + k, oy + k),
        "topright": (ox + k + MID, oy, ox + k + MID, oy + k),
        "bottomleft": (ox, oy + k + MID, ox + k, oy + k + MID),
        "bottomright": (ox + k + MID, oy + k + MID, ox + k + MID, oy + k + MID),
    }
    for name, (x, y, cx, cy) in corners.items():
        out.append(f'<g id="shadow-{name}"><rect x="{x}" y="{y}" width="{k}" height="{k}" '
                   f'fill="url(#sh-r-{name})"/></g>')
    sides = {
        "top": (ox + k, oy, MID, k, "sh-v-top"),
        "bottom": (ox + k, oy + k + MID, MID, k, "sh-v-bottom"),
        "left": (ox, oy + k, k, MID, "sh-h-left"),
        "right": (ox + k + MID, oy + k, k, MID, "sh-h-right"),
    }
    for name, (x, y, w, h, grad) in sides.items():
        out.append(f'<g id="shadow-{name}"><rect x="{x}" y="{y}" width="{w}" height="{h}" '
                   f'fill="url(#{grad})"/></g>')
    out.append(f'<g id="shadow-center"><rect x="{ox + k}" y="{oy + k}" width="{MID}" height="{MID}" '
               f'fill="#000" fill-opacity="0"/></g>')
    stops = ('<stop offset="0" stop-color="#02040c" stop-opacity="0.42"/>'
             '<stop offset="0.45" stop-color="#02040c" stop-opacity="0.16"/>'
             '<stop offset="1" stop-color="#02040c" stop-opacity="0"/>')
    defs = []
    for name, (x, y, cx, cy) in corners.items():
        defs.append(f'<radialGradient id="sh-r-{name}" gradientUnits="userSpaceOnUse" '
                    f'cx="{cx}" cy="{cy}" r="{k}">{stops}</radialGradient>')
    defs += [
        f'<linearGradient id="sh-v-top" x1="0" y1="1" x2="0" y2="0">{stops}</linearGradient>',
        f'<linearGradient id="sh-v-bottom" x1="0" y1="0" x2="0" y2="1">{stops}</linearGradient>',
        f'<linearGradient id="sh-h-left" x1="1" y1="0" x2="0" y2="0">{stops}</linearGradient>',
        f'<linearGradient id="sh-h-right" x1="0" y1="0" x2="1" y2="0">{stops}</linearGradient>',
    ]
    return "".join(defs), "\n".join(out)


def hints(ox: float, oy: float) -> str:
    m = MARGIN
    return (f'<rect id="hint-top-margin" x="{ox}" y="{oy}" width="{m}" height="{m}" fill="none"/>'
            f'<rect id="hint-bottom-margin" x="{ox + 8}" y="{oy}" width="{m}" height="{m}" fill="none"/>'
            f'<rect id="hint-left-margin" x="{ox + 16}" y="{oy}" width="{m}" height="{m}" fill="none"/>'
            f'<rect id="hint-right-margin" x="{ox + 24}" y="{oy}" width="{m}" height="{m}" fill="none"/>'
            f'<rect id="hint-stretch-borders" x="{ox + 32}" y="{oy}" width="2" height="2" fill="none"/>')


def panel_svg(opacity: float) -> str:
    size = 2 * R + MID
    sdefs, sh = shadow(0, size + 10)
    body = "\n".join([
        frame("", "#0e1322", opacity, "#8fd8ff", 0.20, 0.10, 0, 0),
        # Маска размытия: сплошной силуэт, иначе полупрозрачный фон даёт «дырявый» blur
        frame("mask", "#000000", 1.0, "#000000", 0.0, 0.0, size + 10, 0),
        sh,
        hints(0, size + 10 + 2 * SH + MID + 10),
    ])
    h = size + 10 + 2 * SH + MID + 20
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{2 * size + 10}" height="{h}">\n'
            f'<defs>{sdefs}</defs>\n{body}\n</svg>\n')


LINE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40">
<defs>
<linearGradient id="v" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#8fd8ff" stop-opacity="0"/>
<stop offset="0.5" stop-color="#8fd8ff" stop-opacity="0.45"/>
<stop offset="1" stop-color="#8fd8ff" stop-opacity="0"/>
</linearGradient>
<linearGradient id="h" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="#8fd8ff" stop-opacity="0"/>
<stop offset="0.5" stop-color="#8fd8ff" stop-opacity="0.45"/>
<stop offset="1" stop-color="#8fd8ff" stop-opacity="0"/>
</linearGradient>
</defs>
<rect id="vertical-line" x="2" y="0" width="1" height="40" fill="url(#v)"/>
<rect id="horizontal-line" x="10" y="2" width="30" height="1" fill="url(#h)"/>
</svg>
"""

# Контраст и насыщенность под стеклом: фон «светится» сквозь панель, текст остаётся читаемым
EFFECTS = """[ContrastEffect]
enabled=true
contrast=0.85
intensity=0.9
saturation=1.9

[AdaptiveTransparency]
enabled=true

[BlurBehindEffect]
enabled=true
"""

METADATA_DESKTOP = f"""[Desktop Entry]
Name=AIsktagOS Glass
Comment=Стеклянные панели AIsktagOS: строка меню и плавающий док
X-KDE-PluginInfo-Author=AIsktagOS
X-KDE-PluginInfo-Name=AIsktagOS
X-KDE-PluginInfo-Version=2.0
X-KDE-PluginInfo-License=GPL-2.0-or-later
X-KDE-PluginInfo-EnabledByDefault=true
X-Plasma-API=5.0

[Settings]
FallbackTheme=breeze-dark

{EFFECTS}"""

METADATA_JSON = """{
    "KPlugin": {
        "Authors": [ { "Name": "AIsktagOS" } ],
        "Description": "Стеклянные панели AIsktagOS: строка меню и плавающий док",
        "Id": "AIsktagOS",
        "License": "GPL-2.0-or-later",
        "Name": "AIsktagOS Glass",
        "Version": "2.0"
    },
    "X-Plasma-API": "5.0"
}
"""

PLASMARC = "[Settings]\nFallbackTheme=breeze-dark\n\n" + EFFECTS


def main() -> None:
    variants = {
        "widgets": 0.92,              # композитинг без размытия: почти непрозрачно
        "translucent/widgets": 0.75,  # есть размытие: «матовое стекло»
        "opaque/widgets": 1.0,        # без композитинга
    }
    for sub, op in variants.items():
        d = OUT / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "panel-background.svg").write_text(panel_svg(op), encoding="utf-8")
    (OUT / "widgets/line.svg").write_text(LINE_SVG, encoding="utf-8")
    (OUT / "metadata.desktop").write_text(METADATA_DESKTOP, encoding="utf-8")
    (OUT / "metadata.json").write_text(METADATA_JSON, encoding="utf-8")
    (OUT / "plasmarc").write_text(PLASMARC, encoding="utf-8")
    print("Стиль Plasma AIsktagOS Glass сгенерирован:", OUT)


if __name__ == "__main__":
    main()
