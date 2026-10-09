#!/usr/bin/env python3
"""Тема оформления окон AIsktagOS для KWin (Aurorae) «Aurora Glass».

Что даёт тема:
- полупрозрачный заголовок-«стекло»: KWin размывает фон под ним, потому что в decoration.svg
  есть элементы mask-* (Aurorae передаёт их в setBlurRegion, нужен включённый эффект blur);
- скругление углов 14 px, тонкая светящаяся кромка, блик по верхнему краю;
- двухслойная мягкая тень (рассеянная + контактная) и едва заметное синее свечение у активного окна;
- кнопки заголовка в стиле Windows справа: плоские значки «свернуть / развернуть / закрыть» на стекле,
  при наведении подсвечиваются, «закрыть» краснеет. Заголовок выровнен по левому краю.

Цвета берутся из дизайн-токенов (assets/tokens.py).
Рамка рисуется растром (Pillow, сглаживание за счёт отрисовки в 4x) и нарезается на 9 частей
FrameSvg, кнопки — чистый вектор. Фильтры SVG (feGaussianBlur) не используются: QtSvg их
не поддерживает, поэтому свечение сделано радиальными градиентами.
"""
import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from tokens import rgb

OUT = Path(__file__).resolve().parent.parent / "overlay/usr/share/aurorae/themes/AIsktagOS"

SS = 4                                     # коэффициент суперсэмплинга
PAD_SIDE, PAD_TOP, PAD_BOTTOM = 26, 16, 34  # поля под тень (KWin не отдаёт их под ввод)
RADIUS = 14
TITLE_H = 34
CENTER = 40                                # размер растягиваемой середины

GLOW = rgb("accent")                       # свечение активного окна
RIM = rgb("focus")                         # светящаяся кромка

STATES = {
    # префикс: параметры состояния
    "decoration": dict(
        top=rgb("surface") + (190,), bottom=rgb("bg1") + (205,),   # стекло: градиент заголовка
        rim=RIM + (52,), highlight=(255, 255, 255, 34),
        separator=(255, 255, 255, 14),
        shadow=(150, 70), glow=30),
    "decoration-inactive": dict(
        top=rgb("bg2") + (228,), bottom=rgb("bg1") + (234,),
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
        img = Image.alpha_composite(img, soft(w, h, win, RADIUS, GLOW + (st["glow"],), 7, grow=1))

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


# ---- Кнопки заголовка в стиле Windows ---------------------------------------
BTN_W, BTN_H = 34, 26     # ячейка кнопки (ширина, высота)
BTN_R = 7                 # скругление подсветки при наведении
SW = 1.4                  # толщина значка
CX, CY = BTN_W / 2, BTN_H / 2
RED, RED_PRESSED = "#e5484d", "#c53b40"

GLYPHS = {
    "close": f'<path d="M{CX - 4.5} {CY - 4.5}l9 9M{CX + 4.5} {CY - 4.5}l-9 9"/>',
    "minimize": f'<path d="M{CX - 5} {CY + 0.5}h10"/>',
    "maximize": f'<rect x="{CX - 5}" y="{CY - 4.5}" width="10" height="9" rx="1.5"/>',
    "restore": (f'<rect x="{CX - 5}" y="{CY - 2.5}" width="8" height="7" rx="1.2"/>'
                f'<path d="M{CX - 2.5} {CY - 2.5}V{CY - 4}a1.2 1.2 0 0 1 1.2-1.2H{CX + 4}'
                f'A1.2 1.2 0 0 1 {CX + 5.2} {CY - 4}v6a1.2 1.2 0 0 1-1.2 1.2H{CX + 3}"/>'),
}
INK, INK_INACTIVE, INK_OFF = "#dfe6ff", "#7d849c", "#4a5068"


def button_svg(name: str) -> str:
    states = [
        # имя состояния, цвет значка, непрозрачность значка, цвет подложки или None, непрозрачность подложки
        ("active", INK, 0.92, None, 0),
        ("hover", "#ffffff" if name == "close" else INK, 1.0, RED if name == "close" else "#ffffff",
         1.0 if name == "close" else 0.12),
        ("pressed", "#ffffff" if name == "close" else INK, 1.0, RED_PRESSED if name == "close" else "#ffffff",
         1.0 if name == "close" else 0.2),
        ("inactive", INK_INACTIVE, 0.9, None, 0),
        ("hover-inactive", "#ffffff" if name == "close" else INK, 1.0, RED if name == "close" else "#ffffff",
         1.0 if name == "close" else 0.1),
        ("pressed-inactive", "#ffffff" if name == "close" else INK, 1.0, RED_PRESSED if name == "close" else "#ffffff",
         1.0 if name == "close" else 0.18),
        ("deactivated", INK_OFF, 0.7, None, 0),
        ("deactivated-inactive", INK_OFF, 0.7, None, 0),
    ]
    out = []
    for i, (state, ink, ink_op, bg, bg_op) in enumerate(states):
        x = i * (BTN_W + 2)
        g = [f'<g id="{state}-center">',
             # Невидимый прямоугольник задаёт размер элемента для Aurorae
             f'<rect x="{x}" y="0" width="{BTN_W}" height="{BTN_H}" fill="#000" fill-opacity="0.001"/>']
        if bg:
            g.append(f'<rect x="{x + 1}" y="1" width="{BTN_W - 2}" height="{BTN_H - 2}" rx="{BTN_R}" '
                     f'fill="{bg}" fill-opacity="{bg_op}"/>')
        g.append(f'<g transform="translate({x} 0)" stroke="{ink}" stroke-opacity="{ink_op}" stroke-width="{SW}" '
                 f'stroke-linecap="round" stroke-linejoin="round" fill="none">{GLYPHS[name]}</g>')
        g.append("</g>")
        out.append("".join(g))
    width = len(states) * (BTN_W + 2)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{BTN_H}">\n'
            + "\n".join(out) + "\n</svg>\n")


BUTTONS = tuple(GLYPHS)


RC = f"""[General]
ActiveTextColor=#eef3ff
InactiveTextColor=#7d849c
TitleAlignment=Left
TitleVerticalAlignment=Center
Animation=160
Shadow=true

[Layout]
BorderLeft=0
BorderRight=0
BorderBottom=0
TitleEdgeTop=0
TitleEdgeBottom=0
TitleEdgeLeft=14
TitleEdgeRight=8
TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized=14
TitleEdgeRightMaximized=0
TitleBorderLeft=8
TitleBorderRight=8
TitleHeight={TITLE_H}
TitleHeightMaximized={TITLE_H - 4}
ButtonWidth={BTN_W}
ButtonHeight={BTN_H}
ButtonSpacing=2
ButtonMarginTop={(TITLE_H - BTN_H) // 2}
ButtonMarginTopMaximized={(TITLE_H - 4 - BTN_H) // 2}
ExplicitButtonSpacer=6
PaddingTop={PAD_TOP}
PaddingBottom={PAD_BOTTOM}
PaddingLeft={PAD_SIDE}
PaddingRight={PAD_SIDE}
"""

METADATA_DESKTOP = """[Desktop Entry]
Name=AIsktagOS
Comment=Стеклянная тема окон Aurora Glass: кнопки справа, как в Windows
X-KDE-PluginInfo-Author=AIsktagOS
X-KDE-PluginInfo-Name=AIsktagOS
X-KDE-PluginInfo-Version=3.0
X-KDE-PluginInfo-License=GPL-2.0-or-later
X-KDE-PluginInfo-EnabledByDefault=true
"""

METADATA_JSON = """{
    "KPlugin": {
        "Authors": [ { "Name": "AIsktagOS" } ],
        "Description": "Стеклянная тема окон Aurora Glass: кнопки справа, как в Windows",
        "Id": "AIsktagOS",
        "License": "GPL-2.0-or-later",
        "Name": "AIsktagOS",
        "Version": "3.0"
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
