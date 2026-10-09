"""Aurora — единый дизайн экосистемы (как Human Interface Guidelines у Apple).

Источник правды — ``mindkit/data/tokens.json``: цвета, радиусы, отступы,
шрифты. Из него собираются CSS-переменные для веб-интерфейсов
(Mind Studio, ITIS Browser, FileHub AI, порталы) и стиль Qt для
настольных программ, чтобы всё выглядело как одна система.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

TOKENS_FILE = Path(__file__).resolve().parent / "data" / "tokens.json"


def tokens() -> dict:
    return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))


def _kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def _css_color(value: str) -> str:
    # #rrggbbaa → rgba(): Qt и старые браузеры понимают его надёжнее
    if re.fullmatch(r"#[0-9a-fA-F]{8}", value):
        r, g, b, a = (int(value[i:i + 2], 16) for i in (1, 3, 5, 7))
        return f"rgba({r}, {g}, {b}, {round(a / 255, 3)})"
    return value


def css() -> str:
    """CSS-переменные :root { --mt-… } для любых веб-интерфейсов экосистемы."""
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
    lines.append("}")
    lines.append("")
    lines.append("body.mt { background: var(--mt-bg0); color: var(--mt-text); font-family: var(--mt-font-ui); }")
    lines.append(".mt-card { background: var(--mt-surface); border-radius: var(--mt-radius-md); "
                 "box-shadow: var(--mt-shadow-md); }")
    lines.append(".mt-button { background: var(--mt-accent); color: var(--mt-text); border: 0; "
                 "border-radius: var(--mt-radius-sm); padding: 8px 16px; transition: var(--mt-transition); }")
    lines.append(".mt-button:hover { background: var(--mt-accent-hover); }")
    return "\n".join(lines) + "\n"


def qss() -> str:
    """Базовый стиль Qt (PyQt6) в цветах Aurora."""
    c = {k: _css_color(v) for k, v in tokens()["colors"].items()}
    r = tokens()["radius"]
    return f"""/* Aurora — собрано mindkit design qss */
QWidget {{ background: {c['bg1']}; color: {c['text']}; font-size: 11pt; }}
QLineEdit, QTextEdit, QPlainTextEdit {{ background: {c['surface']}; border: 1px solid {c['surface2']};
  border-radius: {r['sm']}px; padding: 6px; selection-background-color: {c['accent']}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color: {c['focus']}; }}
QPushButton {{ background: {c['accent']}; color: {c['text']}; border: 0; border-radius: {r['sm']}px;
  padding: 6px 14px; }}
QPushButton:hover {{ background: {c['accentHover']}; }}
QPushButton:pressed {{ background: {c['accentStrong']}; }}
QListWidget, QTreeWidget {{ background: {c['bg2']}; border: 0; border-radius: {r['md']}px; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: {c['surface2']}; color: {c['text']}; }}
QToolTip {{ background: {c['surface2']}; color: {c['text']}; border: 0; padding: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c['surface2']}; border-radius: 5px; min-height: 24px; }}
"""
