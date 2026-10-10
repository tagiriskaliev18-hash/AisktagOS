"""Aurora — единый дизайн экосистемы (как Human Interface Guidelines у Apple).

Источник правды — ``mindkit/data/tokens.json`` (цвета, градиенты, движение,
глубина) и ``mindkit/data/icons.json`` (иконки Mind). Из них собираются:

* ``css()`` — CSS-переменные, переливающийся градиент, 3D-кнопки и карточки,
  bounce-анимации и иконки Mind классами ``.mi .mi-<имя>``;
* ``qss()`` — стиль Qt (PyQt6) с градиентными объёмными кнопками;
* ``icon_svg()`` / ``sprite()`` — иконки отдельными SVG и одним спрайтом;
* ``js()`` — крошечный скрипт: наклон карточек за курсором и bounce по клику.

Правило экосистемы (docs/DESIGN.md): никаких эмодзи в интерфейсе, только
иконки Mind; фиолетово-синий градиент переливается; 3D-вставки; bounce.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

DATA = Path(__file__).resolve().parent / "data"
TOKENS_FILE = DATA / "tokens.json"
ICONS_FILE = DATA / "icons.json"

# Готовые файлы для проектов, которые копируют дизайн к себе (vendoring)
BUILD_FILES = {
    "mind-ui.css": lambda: css(),
    "mind-ui.qss": lambda: qss(),
    "mind-ui.js": lambda: js(),
    "mind-icons.svg": lambda: sprite(),
}


def tokens() -> dict:
    return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))


def icons() -> dict[str, str]:
    """Имя иконки → внутренности SVG (24×24, обводка)."""
    data = json.loads(ICONS_FILE.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("$")}


def _kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def _css_color(value: str) -> str:
    # #rrggbbaa → rgba(): Qt и старые браузеры понимают его надёжнее
    if re.fullmatch(r"#[0-9a-fA-F]{8}", value):
        r, g, b, a = (int(value[i:i + 2], 16) for i in (1, 3, 5, 7))
        return f"rgba({r}, {g}, {b}, {round(a / 255, 3)})"
    return value


_SVG_ATTRS = ("viewBox='0 0 24 24' fill='none' stroke-width='2' "
              "stroke-linecap='round' stroke-linejoin='round'")


def _grad_defs(gid: str) -> str:
    stops = tokens()["gradient"]["stops"]
    n = len(stops) - 1
    st = "".join(f"<stop offset='{round(i / n, 3)}' stop-color='{c}'/>" for i, c in enumerate(stops))
    # userSpaceOnUse: у прямых линий нулевая ширина, objectBoundingBox их бы потерял
    return (f"<defs><linearGradient id='{gid}' gradientUnits='userSpaceOnUse' "
            f"x1='2' y1='2' x2='22' y2='22'>{st}</linearGradient></defs>")


def icon_svg(name: str, size: int = 24, gradient: bool = True, color: str = "currentColor") -> str:
    """Отдельная иконка Mind. По умолчанию с фиолетово-синим градиентом (для Qt, файлов, favicon)."""
    body = icons()[name]
    if gradient:
        gid = f"mi-g-{name}"
        return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' {_SVG_ATTRS} "
                f"stroke='url(#{gid})'>{_grad_defs(gid)}{body}</svg>")
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{size}' height='{size}' {_SVG_ATTRS} "
            f"stroke='{color}'>{body}</svg>")


def icon_data_uri(name: str, gradient: bool = False) -> str:
    """data:-адрес иконки. Без градиента — чёрная, удобно как CSS-маска."""
    svg = icon_svg(name, gradient=gradient, color="#000")
    return "data:image/svg+xml," + quote(svg, safe=" '=:/;,()")


def sprite() -> str:
    """Все иконки одним SVG: <svg><use href="mind-icons.svg#mi-inbox"/></svg>. Цвет — currentColor."""
    parts = ["<svg xmlns='http://www.w3.org/2000/svg' style='display:none'>",
             "<!-- Иконки Mind — собрано mindkit design, не править вручную -->"]
    for name, body in icons().items():
        parts.append(f"<symbol id='mi-{name}' {_SVG_ATTRS} stroke='currentColor'>{body}</symbol>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _motion_css(t: dict) -> str:
    m = t["motion"]
    spring = m["spring"]
    return f"""
/* ---------- Переливающийся градиент ---------- */
@keyframes mt-flow {{ 0% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }}
  100% {{ background-position: 0% 50%; }} }}
@keyframes mt-bounce-in {{ 0% {{ opacity: 0; transform: scale(.6) translateY(10px); }}
  55% {{ opacity: 1; transform: scale(1.06) translateY(-2px); }} 75% {{ transform: scale(.97); }}
  100% {{ transform: none; }} }}
@keyframes mt-bounce {{ 0%, 100% {{ transform: none; }} 30% {{ transform: translateY(-6px) scale(1.06); }}
  55% {{ transform: translateY(0) scale(.96); }} 75% {{ transform: translateY(-2px) scale(1.01); }} }}
@keyframes mt-pop {{ 0% {{ transform: scale(1); }} 40% {{ transform: scale({m['pressScale']}); }}
  70% {{ transform: scale(1.05); }} 100% {{ transform: scale(1); }} }}
.mt-gradient {{ background: var(--mt-gradient-flow); background-size: 200% 200%;
  animation: mt-flow var(--mt-shimmer) ease-in-out infinite; }}
.mt-gradient-text {{ background: var(--mt-gradient-flow); background-size: 200% 200%;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: mt-flow var(--mt-shimmer) ease-in-out infinite; }}
.mt-gradient-border {{ border: 1px solid transparent;
  background: linear-gradient(var(--mt-surface), var(--mt-surface)) padding-box,
    var(--mt-gradient-flow) border-box; background-size: 100% 100%, 200% 200%;
  animation: mt-flow var(--mt-shimmer) ease-in-out infinite; }}

/* ---------- Иконки Mind: обводка залита живым градиентом ---------- */
.mi {{ display: inline-block; width: 1.25em; height: 1.25em; flex: none; vertical-align: -0.25em;
  background: var(--mt-gradient-flow); background-size: 200% 200%;
  animation: mt-flow var(--mt-shimmer) ease-in-out infinite;
  -webkit-mask: var(--mi) center / contain no-repeat; mask: var(--mi) center / contain no-repeat;
  transition: transform .35s {spring}; }}
.mi.mi-mono {{ background: currentColor; animation: none; }}
.mi.mi-white {{ background: #fff; animation: none; }}
:is(button, a, .mt-bounce):hover > .mi {{ transform: translateY(-1px) scale(1.12); }}
:is(button, a, .mt-bounce):active > .mi {{ transform: scale(.9); }}

/* ---------- 3D-кнопки ---------- */
.mt-btn, .mt-button {{ position: relative; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  border: 0; border-radius: var(--mt-radius-sm); padding: 9px 18px; color: #fff; font: inherit; font-weight: 600;
  cursor: pointer; background: var(--mt-gradient-flow); background-size: 200% 200%;
  animation: mt-flow var(--mt-shimmer) ease-in-out infinite;
  box-shadow: var(--mt-depth-highlight), var(--mt-depth-raised);
  transition: transform .4s {spring}, box-shadow .25s ease, filter .2s ease; }}
.mt-btn::after, .mt-button::after {{ content: ""; position: absolute; inset: 1px 1px 50% 1px; border-radius: inherit;
  background: linear-gradient(180deg, rgba(255,255,255,.28), rgba(255,255,255,0)); pointer-events: none; }}
.mt-btn:hover, .mt-button:hover {{ transform: translateY({m['hoverLift']}px) scale({m['hoverScale']});
  box-shadow: var(--mt-depth-highlight), var(--mt-depth-glow), var(--mt-depth-raised); filter: saturate(1.15); }}
.mt-btn:active, .mt-button:active {{ transform: translateY(1px) scale({m['pressScale']}); transition-duration: {m['press']};
  box-shadow: var(--mt-depth-highlight), 0 2px 6px rgba(10,5,30,.4); }}
.mt-btn .mi {{ background: #fff; animation: none; }}
.mt-btn-ghost {{ background: var(--mt-gradient-soft); color: var(--mt-text); animation: none;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.12), 0 2px 8px rgba(10,5,30,.25); }}
.mt-btn-ghost .mi {{ background: var(--mt-gradient-flow); background-size: 200% 200%;
  animation: mt-flow var(--mt-shimmer) ease-in-out infinite; }}
.mt-icon-btn {{ display: inline-grid; place-items: center; width: 36px; height: 36px; border: 0;
  border-radius: 12px; background: transparent; color: inherit; cursor: pointer;
  transition: transform .4s {spring}, background .2s ease, box-shadow .2s ease; }}
.mt-icon-btn:hover {{ background: var(--mt-gradient-soft); transform: translateY(-1px) scale(1.08);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.12), 0 4px 14px rgba(91,141,238,.25); }}
.mt-icon-btn:active {{ transform: scale(.9); }}

/* ---------- 3D-карточки и вставки ---------- */
.mt-card {{ background: var(--mt-surface); border-radius: var(--mt-radius-md);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.06), var(--mt-depth-raised); }}
.mt-3d {{ transform-style: preserve-3d; transform: perspective(var(--mt-perspective)) rotateX(var(--mt-rx, 0deg))
  rotateY(var(--mt-ry, 0deg)); transition: transform .5s {spring}, box-shadow .3s ease; }}
.mt-3d:hover {{ --mt-rx: 4deg; --mt-ry: -4deg; box-shadow: inset 0 1px 0 rgba(255,255,255,.1), var(--mt-depth-glow),
  var(--mt-depth-raised); }}
.mt-3d > * {{ transform: translateZ(18px); }}
.mt-orb {{ border-radius: 50%; background: radial-gradient(circle at 30% 28%, rgba(255,255,255,.75), transparent 28%),
  var(--mt-gradient-flow); background-size: 100% 100%, 200% 200%;
  animation: mt-flow var(--mt-shimmer) ease-in-out infinite;
  box-shadow: inset -6px -8px 16px rgba(20,10,60,.45), 0 10px 28px rgba(91,141,238,.45); }}

/* ---------- Bounce ---------- */
.mt-bounce-in {{ animation: mt-bounce-in {m['bounceIn']} {spring} both; }}
.mt-bounce {{ transition: transform .4s {spring}; }}
.mt-bounce:hover {{ transform: translateY({m['hoverLift']}px) scale({m['hoverScale']}); }}
.mt-bounce:active {{ transform: scale({m['pressScale']}); }}
.mt-bouncing {{ animation: mt-bounce .6s {spring}; }}
.mt-popping {{ animation: mt-pop .35s {spring}; }}

@media (prefers-reduced-motion: reduce) {{
  .mt-gradient, .mt-gradient-text, .mt-gradient-border, .mi, .mt-btn, .mt-orb {{ animation: none !important; }}
  .mt-bounce-in, .mt-bouncing, .mt-popping {{ animation: none !important; }}
}}
"""


def css(with_icons: bool = True) -> str:
    """Весь веб-дизайн экосистемы: переменные --mt-…, эффекты Mind и иконки .mi-<имя>."""
    t = tokens()
    lines = [f"/* Aurora {t.get('version', '')} — собрано mindkit design css, не править вручную */", ":root {"]
    for k, v in t["colors"].items():
        lines.append(f"  --mt-{_kebab(k)}: {_css_color(v)};")
    for k, v in t["radius"].items():
        lines.append(f"  --mt-radius-{k}: {v}px;")
    for i, v in enumerate(t["space"], 1):
        lines.append(f"  --mt-space-{i}: {v}px;")
    for k, v in t.get("shadow", {}).items():
        lines.append(f"  --mt-shadow-{k}: {v};")
    font = t.get("font", {})
    lines.append(f"  --mt-font-ui: {font.get('ui', 'system-ui')};")
    lines.append(f"  --mt-font-mono: {font.get('mono', 'monospace')};")
    for k, v in font.get("size", {}).items():
        # Размеры в токенах заданы в pt для Qt; в вебе 1pt ≈ 1.333px
        lines.append(f"  --mt-size-{k}: {round(v * 4 / 3, 1)}px;")
    for app, (bg, fg) in t.get("app_accents", {}).items():
        lines.append(f"  --mt-app-{app}: {bg};")
        lines.append(f"  --mt-app-{app}-on: {fg};")
    lines.append(f"  --mt-transition: {t.get('transition', 'all .2s ease')};")
    for k in ("mind", "flow", "soft"):
        lines.append(f"  --mt-gradient-{k}: {t['gradient'][k]};")
    lines.append(f"  --mt-shimmer: {t['motion']['shimmer']};")
    lines.append(f"  --mt-spring: {t['motion']['spring']};")
    for k in ("highlight", "raised", "glow"):
        lines.append(f"  --mt-depth-{k}: {t['depth'][k]};")
    lines.append(f"  --mt-perspective: {t['depth']['perspective']}px;")
    lines.append("}")
    lines.append("")
    lines.append("body.mt { background: var(--mt-bg0); color: var(--mt-text); font-family: var(--mt-font-ui); }")
    lines.append(_motion_css(t))
    if with_icons:
        lines.append("/* ---------- Иконки: <i class=\"mi mi-inbox\"></i> ---------- */")
        for name in icons():
            lines.append(f".mi-{name} {{ --mi: url(\"{icon_data_uri(name)}\"); }}")
    return "\n".join(lines) + "\n"


def js() -> str:
    """Поведение без зависимостей: наклон [data-mt-tilt] за курсором и bounce у .mt-btn/[data-mt-bounce]."""
    tilt = tokens()["depth"]["tilt"]
    return f"""/* Mind UI — собрано mindkit design js, не править вручную */
(function () {{
  if (window.__mindUI) return; window.__mindUI = true;
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  // 3D: карточка поворачивается за курсором
  document.addEventListener('pointermove', function (e) {{
    if (reduce) return;
    var el = e.target.closest && e.target.closest('[data-mt-tilt]');
    if (!el) return;
    var r = el.getBoundingClientRect();
    var x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
    el.style.setProperty('--mt-rx', (-y * {tilt}).toFixed(2) + 'deg');
    el.style.setProperty('--mt-ry', (x * {tilt}).toFixed(2) + 'deg');
  }});
  document.addEventListener('pointerout', function (e) {{
    var el = e.target.closest && e.target.closest('[data-mt-tilt]');
    if (el && !el.contains(e.relatedTarget)) {{ el.style.removeProperty('--mt-rx'); el.style.removeProperty('--mt-ry'); }}
  }});
  // Bounce по клику
  document.addEventListener('click', function (e) {{
    if (reduce) return;
    var el = e.target.closest && e.target.closest('.mt-btn, .mt-icon-btn, [data-mt-bounce]');
    if (!el) return;
    el.classList.remove('mt-popping'); void el.offsetWidth; el.classList.add('mt-popping');
  }}, true);
  // Иконка по имени: MindUI.icon('inbox') → <i class="mi mi-inbox">
  window.MindUI = {{ icon: function (name, cls) {{
    var i = document.createElement('i'); i.className = 'mi mi-' + name + (cls ? ' ' + cls : '');
    i.setAttribute('aria-hidden', 'true'); return i; }} }};
}})();
"""


def qss() -> str:
    """Стиль Qt (PyQt6): градиентные объёмные кнопки Aurora. Анимации — в mindkit.qtfx."""
    t = tokens()
    c = {k: _css_color(v) for k, v in t["colors"].items()}
    r = t["radius"]
    s = t["gradient"]["stops"]
    grad = ("qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            + ", ".join(f"stop:{round(i / (len(s) - 1), 2)} {v}" for i, v in enumerate(s)) + ")")
    hover = ("qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ab74ef, stop:0.5 #6f9cf3, stop:1 #4df8ff)")
    press = ("qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7f45c7, stop:0.5 #4a76d0, stop:1 #00c8d4)")
    return f"""/* Aurora {t.get('version', '')} — собрано mindkit design qss, не править вручную */
QWidget {{ background: {c['bg1']}; color: {c['text']}; font-size: 11pt; }}
QLineEdit, QTextEdit, QPlainTextEdit {{ background: {c['surface']}; border: 1px solid {c['surface2']};
  border-radius: {r['sm']}px; padding: 6px; selection-background-color: {c['ai']}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {c['aiMid']}; }}
QPushButton {{ background: {grad}; color: #ffffff; border: 0; border-radius: {r['sm']}px;
  border-top: 1px solid rgba(255, 255, 255, 0.35); border-bottom: 2px solid rgba(20, 10, 60, 0.45);
  padding: 6px 14px; font-weight: 600; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {press}; border-top: 2px solid rgba(20, 10, 60, 0.45);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2); padding-top: 7px; padding-bottom: 5px; }}
QPushButton:disabled {{ background: {c['surface2']}; color: {c['muted']}; border: 0; }}
QPushButton[flat="true"], QToolButton {{ background: transparent; border: 0; border-radius: {r['sm']}px; padding: 6px; }}
QPushButton[flat="true"]:hover, QToolButton:hover {{ background: rgba(155, 93, 229, 0.16); }}
QPushButton[flat="true"]:pressed, QToolButton:pressed {{ background: rgba(91, 141, 238, 0.28); }}
QListWidget, QTreeWidget {{ background: {c['bg2']}; border: 0; border-radius: {r['md']}px; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
  stop:0 rgba(155, 93, 229, 0.45), stop:1 rgba(0, 245, 255, 0.18)); color: {c['text']}; }}
QTabBar::tab:selected {{ border-bottom: 2px solid {c['aiMid']}; }}
QProgressBar {{ background: {c['surface']}; border: 0; border-radius: 5px; height: 10px; text-align: center; }}
QProgressBar::chunk {{ background: {grad}; border-radius: 5px; }}
QToolTip {{ background: {c['surface2']}; color: {c['text']}; border: 1px solid {c['ai']}; padding: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c['surface2']}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {c['ai']}; }}
"""


def build(out_dir: str | Path) -> list[Path]:
    """Пишет готовые файлы дизайна (css, qss, js, спрайт и SVG-иконки) в папку проекта."""
    out = Path(out_dir)
    (out / "icons").mkdir(parents=True, exist_ok=True)
    written = []
    for name, make in BUILD_FILES.items():
        p = out / name
        p.write_text(make(), encoding="utf-8")
        written.append(p)
    for name in icons():
        p = out / "icons" / f"{name}.svg"
        p.write_text(icon_svg(name) + "\n", encoding="utf-8")
        written.append(p)
    return written
