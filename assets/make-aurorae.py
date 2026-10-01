#!/usr/bin/env python3
"""Тема оформления окон AIsktagOS для KWin (Aurorae) «Frosted Glass».

Что даёт тема:
- полупрозрачный заголовок-«стекло»: KWin размывает фон под ним, потому что в decoration.svg
  есть элементы mask-* (Aurorae передаёт их в setBlurRegion, нужен включённый эффект blur);
- скругление углов 14 px, тонкая светящаяся кромка, блик по верхнему краю;
- двухслойная мягкая тень (рассеянная + контактная) и едва заметное неоновое свечение
  у активного окна;
- кнопки-«светофор» слева: векторные круги с объёмной заливкой, полупрозрачной рамкой
  и мягким ореолом при наведении/нажатии.

Рамка рисуется растром (Pillow, сглаживание за счёт отрисовки в 4x) и нарезается на 9 частей
FrameSvg, кнопки — чистый вектор. Фильтры SVG (feGaussianBlur) не используются: QtSvg их
не поддерживает, поэтому свечение сделано радиальными градиентами.
"""
import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "overlay/usr/share/aurorae/themes/AIsktagOS"

SS = 4                                     # коэффициент суперсэмплинга
PAD_SIDE, PAD_TOP, PAD_BOTTOM = 26, 16, 34  # поля под тень (KWin не отдаёт их под ввод)
RADIUS = 14
TITLE_H = 34
CENTER = 40                                # размер растягиваемой середины

CYAN = (34, 228, 255)

STATES = {
    # префикс: параметры состояния
    "decoration": dict(
        top=(30, 38, 62, 188), bottom=(18, 24, 42, 200),   # стекло: градиент заголовка
        rim=(150, 215, 255, 64), highlight=(255, 255, 255, 34),
        separator=(255, 255, 255, 14),
        shadow=(150, 70), glow=26),
    "decoration-inactive": dict(
        top=(26, 30, 44, 226), bottom=(20, 23, 34, 232),
        rim=(255, 255, 255, 20), highlight=(255, 255, 255, 14),
        separator=(255, 255, 255, 8),
        shadow=(90, 40), glow=0),
}


def geometry():
    left = PAD_SIDE + RADIUS
    top = PAD_TOP + TITLE_H
    bottom = PAD_BOTTOM + RADIUS
    w = left * 2 + CENTER
    h = top + CENTER + bottom
    win = (PAD_SIDE, PAD_TOP, w - PAD_SIDE, h - PAD_BOTTOM)
    return w, h, win


def scaled(box, dy=0, grow=0):
    x0, y0, x1, y1 = box
    return ((x0 - grow) * SS, (y0 + dy - grow) * SS, (x1 + grow) * SS - 1, (y1 + dy + grow) * SS - 1)


def soft(w, h, box, radius, color, blur, dy=0, grow=0):
    """Размытая скруглённая подложка: из таких слоёв собраны тень и свечение."""
    layer = Image.new("RGBA", (w * SS, h * SS), color[:3] + (0,))
    mask = Image.new("L", layer.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(scaled(box, dy, grow), (radius + grow) * SS, fill=color[3])
    layer.putalpha(mask.filter(ImageFilter.GaussianBlur(blur * SS)))
    return layer


def frame(st: dict) -> Image.Image:
    w, h, win = geometry()
    W, H = w * SS, h * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Тени: широкая рассеянная и плотная контактная
    ambient, contact = st["shadow"]
    img = Image.alpha_composite(img, soft(w, h, win, RADIUS, (0, 0, 0, ambient), 13, dy=9))
    img = Image.alpha_composite(img, soft(w, h, win, RADIUS, (0, 0, 0, contact), 3, dy=2))
    if st["glow"]:
        img = Image.alpha_composite(img, soft(w, h, win, RADIUS, CYAN + (st["glow"],), 7, grow=1))

    # Тень не должна просвечивать сквозь стекло: вырезаем её под силуэтом окна
    shape = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shape).rounded_rectangle(scaled(win), RADIUS * SS, fill=255)
    img.putalpha(Image.composite(Image.new("L", (W, H), 0), img.getchannel("A"), shape))

    # Стекло: вертикальный градиент в пределах заголовка, ниже — ровный тон
    body = Image.new("RGBA", (W, H))
    px = ImageDraw.Draw(body)
    y_title_end = (PAD_TOP + TITLE_H) * SS
    for y in range(H):
        t = min(max((y - PAD_TOP * SS) / (TITLE_H * SS), 0.0), 1.0)
        c = tuple(round(a + (b - a) * t) for a, b in zip(st["top"], st["bottom"]))
        px.line((0, y, W, y), fill=c)
    body.putalpha(Image.composite(body.getchannel("A"), Image.new("L", (W, H), 0), shape))
    img = Image.alpha_composite(img, body)

    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(deco)
    x0, y0, x1, y1 = scaled(win)
    # Разделитель между заголовком и содержимым окна
    d.line((x0, y_title_end - SS, x1, y_title_end - SS), fill=st["separator"], width=SS)
    # Блик по верхней кромке (внутри рамки)
    d.rounded_rectangle((x0 + SS, y0 + SS, x1 - SS, y1 - SS), (RADIUS - 1) * SS,
                        outline=st["highlight"], width=SS)
    # Блик нужен только сверху: всё, что ниже скругления, срезаем (разделитель оставляем)
    cut = Image.new("L", (W, H), 255)
    ImageDraw.Draw(cut).rectangle((0, y0 + (RADIUS + 6) * SS, W, y_title_end - 2 * SS), fill=0)
    ImageDraw.Draw(cut).rectangle((0, y_title_end, W, H), fill=0)
    deco.putalpha(Image.composite(deco.getchannel("A"), Image.new("L", (W, H), 0), cut))
    img = Image.alpha_composite(img, deco)

    # Светящаяся кромка по всему контуру
    rim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle((x0, y0, x1, y1), RADIUS * SS, outline=st["rim"], width=SS)
    img = Image.alpha_composite(img, rim)
    return img.resize((w, h), Image.LANCZOS)


def mask_frame() -> Image.Image:
    """Область размытия: непрозрачный силуэт окна без тени."""
    w, h, win = geometry()
    m = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    ImageDraw.Draw(m).rounded_rectangle(scaled(win), RADIUS * SS, fill=(0, 0, 0, 255))
    return m.resize((w, h), Image.LANCZOS)


def png_b64(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def decoration_svg() -> str:
    w, h, _ = geometry()
    left = PAD_SIDE + RADIUS
    top = PAD_TOP + TITLE_H
    bottom = PAD_BOTTOM + RADIUS
    cols = [(0, left), (left, CENTER), (left + CENTER, left)]
    rows = [(0, top), (top, CENTER), (top + CENTER, bottom)]
    names = [["topleft", "top", "topright"], ["left", "center", "right"],
             ["bottomleft", "bottom", "bottomright"]]
    images = [(p, frame(st)) for p, st in STATES.items()] + [("mask", mask_frame())]
    parts = []
    offset_y = 0
    for prefix, im in images:
        for r, (y, hh) in enumerate(rows):
            for c, (x, ww) in enumerate(cols):
                piece = im.crop((x, y, x + ww, y + hh))
                parts.append(
                    f'<image id="{prefix}-{names[r][c]}" x="{x}" y="{y + offset_y}" '
                    f'width="{ww}" height="{hh}" preserveAspectRatio="none" '
                    f'xlink:href="data:image/png;base64,{png_b64(piece)}"/>')
        offset_y += h + 20
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{offset_y}">\n' + "\n".join(parts) + "\n</svg>\n")


# ---- Кнопки-«светофор» -------------------------------------------------------
BTN = 18          # ячейка кнопки (место под ореол)
R = 6.5           # радиус круга
C = BTN / 2

BUTTONS = {
    # файл: (основной цвет, светлый, тёмный, цвет значка, значок)
    "close": ("#ff5f57", "#ff9a92", "#d93c34", "#5c0a06",
              '<path d="M6.6 6.6l4.8 4.8M11.4 6.6l-4.8 4.8"/>'),
    "minimize": ("#febc2e", "#ffdb7a", "#d9960f", "#5e3a00", '<path d="M6 9h6"/>'),
    "maximize": ("#28c840", "#74e57f", "#159a2b", "#063d0e",
                 '<path d="M6.3 9h5.4M9 6.3v5.4"/>'),
    "restore": ("#28c840", "#74e57f", "#159a2b", "#063d0e", '<path d="M6.3 9h5.4"/>'),
}

GRAPHITE = ("#3b4257", "#566079", "#2a3042")
DISABLED = ("#2c3142", "#363c50", "#232736")


def gradients(uid: str, base: str, light: str, dark: str) -> str:
    return (
        f'<radialGradient id="f-{uid}" cx="0.38" cy="0.32" r="0.75">'
        f'<stop offset="0" stop-color="{light}"/><stop offset="0.55" stop-color="{base}"/>'
        f'<stop offset="1" stop-color="{dark}"/></radialGradient>'
        f'<radialGradient id="g-{uid}" cx="0.5" cy="0.5" r="0.5">'
        f'<stop offset="0.55" stop-color="{base}" stop-opacity="0.55"/>'
        f'<stop offset="0.78" stop-color="{base}" stop-opacity="0.18"/>'
        f'<stop offset="1" stop-color="{base}" stop-opacity="0"/></radialGradient>')


def button_svg(name: str) -> str:
    base, light, dark, ink, glyph = BUTTONS[name]
    states = [
        # имя, палитра, значок, ореол, затемнение
        ("active", "c", False, 0.0, 0.0),
        ("hover", "c", True, 1.0, 0.0),
        ("pressed", "c", True, 0.7, 0.28),
        ("inactive", "g", False, 0.0, 0.0),
        ("hover-inactive", "c", True, 1.0, 0.0),
        ("pressed-inactive", "c", True, 0.7, 0.28),
        ("deactivated", "d", False, 0.0, 0.0),
        ("deactivated-inactive", "d", False, 0.0, 0.0),
    ]
    defs = (gradients("c", base, light, dark) + gradients("g", *GRAPHITE)
            + gradients("d", *DISABLED)
            + '<linearGradient id="shine" x1="0" y1="0" x2="0" y2="1">'
              '<stop offset="0" stop-color="#fff" stop-opacity="0.55"/>'
              '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    out = []
    for i, (state, pal, show_glyph, halo, shade) in enumerate(states):
        x = i * (BTN + 2)
        g = [f'<g id="{state}-center">',
             # Невидимый прямоугольник задаёт размер элемента для Aurorae
             f'<rect x="{x}" y="0" width="{BTN}" height="{BTN}" fill="#000" fill-opacity="0.001"/>']
        if halo:
            g.append(f'<circle cx="{x + C}" cy="{C}" r="{C}" fill="url(#g-{pal})" opacity="{halo}"/>')
        g.append(f'<circle cx="{x + C}" cy="{C}" r="{R}" fill="url(#f-{pal})"/>')
        if shade:
            g.append(f'<circle cx="{x + C}" cy="{C}" r="{R}" fill="#000" fill-opacity="{shade}"/>')
        # Стеклянный блик в верхней половине
        g.append(f'<ellipse cx="{x + C}" cy="{C - 2.6}" rx="{R * 0.62:.2f}" ry="{R * 0.42:.2f}" '
                 f'fill="url(#shine)" opacity="{0.35 if pal == "c" else 0.18}"/>')
        # Полупрозрачная двойная рамка: тёмная снаружи, светлая внутри
        g.append(f'<circle cx="{x + C}" cy="{C}" r="{R - 0.3}" fill="none" stroke="#000" '
                 f'stroke-opacity="0.32" stroke-width="0.6"/>')
        g.append(f'<circle cx="{x + C}" cy="{C}" r="{R - 1}" fill="none" stroke="#fff" '
                 f'stroke-opacity="{0.22 if pal == "c" else 0.08}" stroke-width="0.6"/>')
        if show_glyph:
            g.append(f'<g transform="translate({x} 0)" stroke="{ink}" stroke-opacity="0.8" '
                     f'stroke-width="1.5" stroke-linecap="round" fill="none">{glyph}</g>')
        g.append("</g>")
        out.append("".join(g))
    width = len(states) * (BTN + 2)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{BTN}">\n'
            f'<defs>{defs}</defs>\n' + "\n".join(out) + "\n</svg>\n")


RC = f"""[General]
ActiveTextColor=#eef3ff
InactiveTextColor=#7d849c
TitleAlignment=Center
TitleVerticalAlignment=Center
Animation=160
Shadow=true

[Layout]
BorderLeft=0
BorderRight=0
BorderBottom=0
TitleEdgeTop=0
TitleEdgeBottom=0
TitleEdgeLeft=12
TitleEdgeRight=12
TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized=12
TitleEdgeRightMaximized=12
TitleBorderLeft=8
TitleBorderRight=8
TitleHeight={TITLE_H}
TitleHeightMaximized={TITLE_H - 4}
ButtonWidth={BTN}
ButtonHeight={BTN}
ButtonSpacing=2
ButtonMarginTop={(TITLE_H - BTN) // 2}
ButtonMarginTopMaximized={(TITLE_H - 4 - BTN) // 2}
ExplicitButtonSpacer=10
PaddingTop={PAD_TOP}
PaddingBottom={PAD_BOTTOM}
PaddingLeft={PAD_SIDE}
PaddingRight={PAD_SIDE}
"""

METADATA_DESKTOP = """[Desktop Entry]
Name=AIsktagOS
Comment=Стеклянная тема окон с кнопками-«светофором»
X-KDE-PluginInfo-Author=AIsktagOS
X-KDE-PluginInfo-Name=AIsktagOS
X-KDE-PluginInfo-Version=2.0
X-KDE-PluginInfo-License=GPL-2.0-or-later
X-KDE-PluginInfo-EnabledByDefault=true
"""

METADATA_JSON = """{
    "KPlugin": {
        "Authors": [ { "Name": "AIsktagOS" } ],
        "Description": "Стеклянная тема окон с кнопками-«светофором»",
        "Id": "AIsktagOS",
        "License": "GPL-2.0-or-later",
        "Name": "AIsktagOS",
        "Version": "2.0"
    }
}
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "decoration.svg").write_text(decoration_svg(), encoding="utf-8")
    for name in BUTTONS:
        (OUT / f"{name}.svg").write_text(button_svg(name), encoding="utf-8")
    (OUT / "AIsktagOSrc").write_text(RC, encoding="utf-8")
    (OUT / "metadata.desktop").write_text(METADATA_DESKTOP, encoding="utf-8")
    (OUT / "metadata.json").write_text(METADATA_JSON, encoding="utf-8")
    print("Тема окон AIsktagOS сгенерирована:", OUT)


if __name__ == "__main__":
    main()
