#!/usr/bin/env python3
"""Генерирует графику AIsktagOS: логотипы, обои, фон GRUB, заставку загрузки, картинки установщика.

Запуск (нужны python3-numpy, python3-pil; для логотипов и значков — rsvg-convert и шрифт Inter):
    python3 assets/make-assets.py                 # всё
    python3 assets/make-assets.py grub slides     # только выбранные части
Части: icons (логотипы, значки, Plymouth, баннер установщика), wallpapers (обои),
grub (тема меню загрузки), slides (фон слайдов установщика).
Результат раскладывается по overlay/ и iso/; повторный запуск перезаписывает файлы.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OS = Path(__file__).resolve().parent.parent
ASSETS = OS / "assets"
OVERLAY = OS / "overlay"

# Палитра AIsktagOS: глубокий индиго -> фиолетовый -> бирюзовый
BG = (9, 12, 28)
BLOBS = [  # (x, y, радиус, цвет) в долях экрана
    (0.18, 0.78, 0.55, (91, 76, 255)),
    (0.72, 0.30, 0.50, (34, 211, 238)),
    (0.95, 0.95, 0.45, (236, 72, 153)),
    (0.45, 0.10, 0.40, (139, 92, 246)),
    (0.05, 0.10, 0.35, (37, 99, 235)),
]

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#6d5dfc"/>
      <stop offset="0.55" stop-color="#8b5cf6"/>
      <stop offset="1" stop-color="#22d3ee"/>
    </linearGradient>
    <linearGradient id="shine" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.28"/>
      <stop offset="0.5" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect x="8" y="8" width="240" height="240" rx="56" fill="url(#bg)"/>
  <rect x="8" y="8" width="240" height="240" rx="56" fill="url(#shine)"/>
  <circle cx="100" cy="128" r="58" fill="none" stroke="#ffffff" stroke-width="20"/>
  <circle cx="156" cy="128" r="58" fill="none" stroke="#ffffff" stroke-opacity="0.72" stroke-width="20"/>
</svg>
"""

# Монохромный значок для верхней панели (аналог «яблока» в строке меню)
LOGO_SYMBOLIC_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">
  <style type="text/css" id="current-color-scheme">.ColorScheme-Text { color:#fcfcfc; }</style>
  <g class="ColorScheme-Text" fill="none" stroke="currentColor" stroke-width="1.6">
    <circle cx="6" cy="8" r="4.2"/>
    <circle cx="10" cy="8" r="4.2" stroke-opacity="0.7"/>
  </g>
</svg>
"""

# Значок «Установить AIsktagOS» для рабочего стола live-сессии
INSTALL_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#6d5dfc"/><stop offset="1" stop-color="#22d3ee"/>
    </linearGradient>
  </defs>
  <rect x="8" y="8" width="240" height="240" rx="56" fill="url(#bg)"/>
  <path d="M128 52v104M84 116l44 44 44-44" fill="none" stroke="#fff" stroke-width="22"
        stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="64" y="182" width="128" height="22" rx="11" fill="#fff"/>
</svg>
"""


def wallpaper(w: int, h: int, darken: float = 1.0) -> Image.Image:
    """Мягкий «жидкий» градиент в духе обоев macOS."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xx /= w
    yy /= h
    aspect = w / h
    img = np.zeros((h, w, 3), np.float32) + np.array(BG, np.float32)
    for bx, by, r, col in BLOBS:
        d2 = ((xx - bx) * aspect) ** 2 + (yy - by) ** 2
        a = np.exp(-d2 / (2 * (r * 0.55) ** 2))[..., None] * 0.85
        img = img * (1 - a) + np.array(col, np.float32) * a
    # Лёгкие диагональные волны — объём без рисунка
    waves = 0.5 + 0.5 * np.sin((xx * 3.1 + yy * 1.7) * np.pi + np.sin(yy * 4.0) * 0.8)
    img *= (0.82 + 0.18 * waves)[..., None]
    # Виньетка
    v = 1 - 0.35 * (((xx - 0.5) * 1.6) ** 2 + ((yy - 0.5) * 1.6) ** 2)
    img *= np.clip(v, 0.55, 1)[..., None] * darken
    # Шум против полос градиента
    img += np.random.default_rng(7).normal(0, 1.2, img.shape)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))


def svg_to_png(svg: str, out: Path, size: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), "-o", str(out)],
                   input=svg.encode(), check=True)


def text_png(svg: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsvg-convert", "-o", str(out)], input=svg.encode(), check=True)


def logo_image(size: int) -> Image.Image:
    """Логотип нужного размера: через rsvg-convert, а без него — из готового logo.png."""
    if shutil.which("rsvg-convert"):
        tmp = Path(tempfile.gettempdir()) / f"aisktagos-logo-{size}.png"
        svg_to_png(LOGO_SVG, tmp, size)
        return Image.open(tmp).convert("RGBA")
    return Image.open(OVERLAY / "usr/share/aisktagos/logo.png").convert("RGBA").resize(
        (size, size), Image.LANCZOS)


def glow(size, center, radius, color, strength):
    """Мягкое световое пятно (RGBA) для «кинематографичных» фонов."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d2 = ((xx - center[0]) / radius[0]) ** 2 + ((yy - center[1]) / radius[1]) ** 2
    a = np.exp(-d2 * 2.2) * strength
    img = np.zeros((h, w, 4), np.float32)
    img[..., :3] = color
    img[..., 3] = np.clip(a, 0, 1) * 255
    return Image.fromarray(img.astype(np.uint8), "RGBA")


def cinematic(w: int, h: int) -> Image.Image:
    """Тёмный широкоэкранный фон: обои, приглушённые к краям, световой горизонт и кромки кадра."""
    src = OVERLAY / "usr/share/wallpapers/AIsktagOS/contents/images/3840x2160.jpg"
    base = (Image.open(src).convert("RGB").resize((w, h), Image.LANCZOS)
            if src.exists() else wallpaper(w, h))
    a = np.asarray(base, np.float32) * 0.42
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xx /= w
    yy /= h
    # Сильная виньетка и затемнение сверху/снизу, как у кадра с широкоэкранными полями
    v = 1 - 0.85 * (((xx - 0.5) * 1.35) ** 2 + ((yy - 0.48) * 1.6) ** 2)
    a *= np.clip(v, 0.18, 1)[..., None]
    bars = np.clip(1 - np.maximum(0.10 - yy, yy - 0.90) / 0.10, 0.35, 1)
    a *= bars[..., None]
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
    # Световой горизонт: широкая неоново-синяя дымка и тонкая циановая линия
    img = Image.alpha_composite(img, glow((w, h), (w * 0.5, h * 0.47), (w * 0.42, h * 0.16),
                                          (61, 123, 255), 0.34))
    img = Image.alpha_composite(img, glow((w, h), (w * 0.5, h * 0.47), (w * 0.30, h * 0.012),
                                          (34, 228, 255), 0.55))
    # Мелкий шум — без полос на градиентах
    n = np.random.default_rng(11).normal(0, 1.6, (h, w, 1))
    a = np.asarray(img, np.float32)
    a[..., :3] += n
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA").convert("RGB")


def rounded(w, h, r, fill, outline=None, ss=4):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=fill,
                                         outline=outline, width=ss if outline else 0)
    return im.resize((w, h), Image.LANCZOS)


def hgradient(w, h, start, end):
    """Горизонтальный градиент RGBA."""
    g = np.zeros((h, w, 4), np.float32)
    t = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    for i in range(3):
        g[..., i] = start[i] + (end[i] - start[i]) * t
    g[..., 3] = 255
    return Image.fromarray(g.astype(np.uint8), "RGBA")


def slice9(im: Image.Image, prefix: str, out: Path, b: int) -> None:
    """Нарезка картинки на 9 частей для стилей GRUB (*_nw.png … *_se.png)."""
    w, h = im.size
    xs = [(0, b), (b, w - b), (w - b, w)]
    ys = [(0, b), (b, h - b), (h - b, h)]
    names = [["nw", "n", "ne"], ["w", "c", "e"], ["sw", "s", "se"]]
    for r, (y0, y1) in enumerate(ys):
        for c, (x0, x1) in enumerate(xs):
            im.crop((x0, y0, x1, y1)).save(out / f"{prefix}_{names[r][c]}.png", optimize=True)


def slice3(im: Image.Image, prefix: str, out: Path, b: int) -> None:
    """Горизонтальная полоса из трёх частей (*_w, *_c, *_e)."""
    w, h = im.size
    for name, (x0, x1) in (("w", (0, b)), ("c", (b, w - b)), ("e", (w - b, w))):
        im.crop((x0, 0, x1, h)).save(out / f"{prefix}_{name}.png", optimize=True)


def make_grub() -> None:
    out = OS / "iso/theme"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()

    # Фон: кинематографичный кадр + логотип со свечением (название рисует сама тема шрифтом Inter)
    bg = cinematic(1920, 1080).convert("RGBA")
    bg = Image.alpha_composite(bg, glow(bg.size, (960, 300), (150, 150), (61, 123, 255), 0.45))
    bg = Image.alpha_composite(bg, glow(bg.size, (960, 300), (90, 90), (34, 228, 255), 0.25))
    logo = logo_image(120)
    bg.paste(logo, (900, 240), logo)
    bg.convert("RGB").save(out / "background.png", optimize=True)

    # Стеклянная подложка меню
    slice9(rounded(64, 64, 18, (14, 19, 36, 150), (143, 216, 255, 40)), "menu", out, 22)
    # Окно консоли GRUB (клавиша C) в том же стиле
    slice9(rounded(64, 64, 14, (8, 11, 22, 235), (143, 216, 255, 50)), "terminal_box", out, 18)

    # Светящийся селектор пункта: капсула с градиентом, циановой кромкой и ореолом
    H, W, ss = 46, 96, 4
    pill = (5 * ss, 6 * ss, (W - 5) * ss - 1, (H - 6) * ss - 1)
    sel = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    halo = Image.new("L", sel.size, 0)
    ImageDraw.Draw(halo).rounded_rectangle((4 * ss, 5 * ss, (W - 4) * ss, (H - 5) * ss), 18 * ss, fill=120)
    sel.paste(Image.new("RGBA", sel.size, (34, 228, 255, 255)), (0, 0),
              halo.filter(ImageFilter.GaussianBlur(3 * ss)))
    shape = Image.new("L", sel.size, 0)
    ImageDraw.Draw(shape).rounded_rectangle(pill, 17 * ss, fill=255)
    # Внутри капсулы ореол не нужен: там своя заливка
    sel.putalpha(Image.composite(Image.new("L", sel.size, 0), sel.getchannel("A"), shape))
    body = Image.new("RGBA", sel.size, (0, 0, 0, 0))
    body.paste(hgradient(W * ss, H * ss, (31, 160, 255), (61, 107, 255)), (0, 0),
               shape.point(lambda v: v * 92 // 255))
    sel = Image.alpha_composite(sel, body)
    ImageDraw.Draw(sel).rounded_rectangle(pill, 17 * ss, outline=(120, 236, 255, 210), width=ss)
    slice3(sel.resize((W, H), Image.LANCZOS), "select", out, 24)

    # Полоса таймера: тёмная дорожка и неоновая заливка
    slice3(rounded(48, 6, 3, (255, 255, 255, 28)), "progress_bar", out, 3)
    fill = Image.new("RGBA", (48 * 4, 6 * 4), (0, 0, 0, 0))
    m = Image.new("L", fill.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, 48 * 4 - 1, 6 * 4 - 1), 12, fill=255)
    fill.paste(hgradient(48 * 4, 6 * 4, (34, 228, 255), (61, 123, 255)), (0, 0), m)
    slice3(fill.resize((48, 6), Image.LANCZOS), "progress_highlight", out, 3)


def make_calamares_slides() -> None:
    cal = OVERLAY / "etc/calamares/branding/aisktagos"
    cal.mkdir(parents=True, exist_ok=True)
    bg = cinematic(1280, 720).convert("RGBA")
    bg = Image.alpha_composite(bg, glow(bg.size, (1050, 120), (420, 300), (34, 228, 255), 0.16))
    bg.convert("RGB").save(cal / "slide-bg.jpg", quality=90)


def make_icons_and_logos() -> None:
    icons = OVERLAY / "usr/share/icons/hicolor"
    (icons / "scalable/apps").mkdir(parents=True, exist_ok=True)
    (icons / "scalable/apps/aisktagos-logo.svg").write_text(LOGO_SVG, encoding="utf-8")
    (icons / "scalable/apps/aisktagos-logo-symbolic.svg").write_text(LOGO_SYMBOLIC_SVG, encoding="utf-8")
    (icons / "scalable/apps/aisktagos-install.svg").write_text(INSTALL_SVG, encoding="utf-8")
    for s in (16, 22, 24, 32, 48, 64, 128, 256):
        svg_to_png(LOGO_SVG, icons / f"{s}x{s}/apps/aisktagos-logo.png", s)
        svg_to_png(INSTALL_SVG, icons / f"{s}x{s}/apps/aisktagos-install.png", s)
    share = OVERLAY / "usr/share/aisktagos"
    svg_to_png(LOGO_SVG, share / "logo.png", 256)
    # Загрузочная заставка (Plymouth): логотип по центру + подпись внизу
    svg_to_png(LOGO_SVG, share / "plymouth-logo.png", 160)
    text_png("""<svg xmlns="http://www.w3.org/2000/svg" width="300" height="56">
      <text x="150" y="42" text-anchor="middle" font-family="Inter" font-weight="600"
            font-size="36" fill="#ffffff">AIsktagOS</text></svg>""", share / "plymouth-watermark.png")
    # Установщик Calamares: логотипы и баннер приветствия
    cal = OVERLAY / "etc/calamares/branding/aisktagos"
    cal.mkdir(parents=True, exist_ok=True)
    svg_to_png(LOGO_SVG, cal / "logo.png", 128)
    svg_to_png(LOGO_SVG, cal / "icon.png", 64)
    welcome = wallpaper(960, 360, darken=0.8)
    logo = logo_image(120)
    welcome.paste(logo, (140, 120), logo)
    tmp = Path(tempfile.gettempdir()) / "aisktagos-welcome-text.png"
    text_png("""<svg xmlns="http://www.w3.org/2000/svg" width="620" height="200">
      <text x="0" y="80" font-family="Inter" font-weight="700" font-size="72" fill="#fff">AIsktagOS</text>
      <text x="4" y="130" font-family="Inter" font-size="28" fill="#e0e7ff">Операционная система для разработчиков</text>
      </svg>""", tmp)
    wt = Image.open(tmp)
    welcome.paste(wt, (300, 105), wt)
    welcome.save(cal / "welcome.png", optimize=True)
    # Фото пользователя по умолчанию
    svg_to_png(LOGO_SVG, OVERLAY / "etc/skel/.face", 192)


def make_wallpapers() -> None:
    wp = OVERLAY / "usr/share/wallpapers/AIsktagOS/contents/images"
    wp.mkdir(parents=True, exist_ok=True)
    big = wallpaper(3840, 2160)
    big.save(wp / "3840x2160.jpg", quality=92)
    big.resize((1920, 1080), Image.LANCZOS).save(wp / "1920x1080.jpg", quality=92)
    big.resize((400, 225), Image.LANCZOS).save(wp.parent / "screenshot.jpg", quality=90)


PARTS = {
    # имя: (функция, нужен ли rsvg-convert)
    "icons": (make_icons_and_logos, True),
    "wallpapers": (make_wallpapers, False),
    "grub": (make_grub, False),
    "slides": (make_calamares_slides, False),
}


def main() -> None:
    wanted = sys.argv[1:] or list(PARTS)
    unknown = [p for p in wanted if p not in PARTS]
    if unknown:
        sys.exit(f"Неизвестные части: {', '.join(unknown)}. Доступны: {', '.join(PARTS)}")
    for name in wanted:
        fn, needs_rsvg = PARTS[name]
        if needs_rsvg and not shutil.which("rsvg-convert"):
            sys.exit(f"Для части «{name}» нужен rsvg-convert (пакет librsvg2-bin). "
                     f"Без него можно собрать: {', '.join(p for p, (_f, r) in PARTS.items() if not r)}")
        fn()
        print(f"Готово: {name}")
    print("Графика AIsktagOS сгенерирована")


if __name__ == "__main__":
    main()
