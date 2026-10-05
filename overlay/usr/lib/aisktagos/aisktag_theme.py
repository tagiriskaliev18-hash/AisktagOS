"""Тема «Aurora» для PyQt-приложений AIsktagOS (Центр, Mind). Цвета берутся из дизайн-токенов
/usr/share/aisktagos/design/tokens.json (их генерирует assets/tokens.py), чтобы все окна совпадали по палитре."""
from __future__ import annotations

import json
import os
from pathlib import Path

_TOKENS_FILE = Path(os.environ.get("AISKTAG_TOKENS", "/usr/share/aisktagos/design/tokens.json"))
_FALLBACK = {
    "bg0": "#070b16", "bg1": "#0b1020", "bg2": "#111a33", "surface": "#16203d", "surface2": "#1e2a50",
    "text": "#eef3ff", "text2": "#b8c2e0", "muted": "#8f9abf", "accent": "#3d7bff", "accentStrong": "#2a5be0",
    "focus": "#22e4ff", "ai": "#8b5cf6", "aiText": "#b79cff", "ok": "#2fd27a", "warn": "#febc2e", "danger": "#ff5f57",
}


def _load() -> dict:
    try:
        return {**_FALLBACK, **json.loads(_TOKENS_FILE.read_text(encoding="utf-8"))["colors"]}
    except (OSError, ValueError, KeyError):
        return dict(_FALLBACK)


C = _load()


def rgba(name: str, alpha: float) -> str:
    h = C[name]
    return f"rgba({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)}, {alpha})"


def base_qss() -> str:
    """Общие стили: шрифт, кнопки, поля ввода, полосы прокрутки, карточки."""
    return f"""
QWidget {{ font-family: Inter; font-size: 10.5pt; color: {C['text']}; }}
QWidget#root {{ background: {C['bg1']}; }}
QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QToolTip {{ background: {C['surface2']}; color: {C['text']}; border: 1px solid {rgba('focus', 0.35)}; padding: 4px 8px; }}

QLabel#h1 {{ font-size: 22pt; font-weight: 600; color: {C['text']}; }}
QLabel#h2 {{ font-size: 13.5pt; font-weight: 600; color: {C['text']}; }}
QLabel#muted {{ color: {C['muted']}; }}

QFrame#card {{ background: {C['surface']}; border: 1px solid {rgba('focus', 0.14)}; border-radius: 14px; }}
QFrame#bar {{ background: {C['bg2']}; border: none; border-bottom: 1px solid {rgba('focus', 0.12)}; }}

QPushButton {{ background: {C['surface']}; border: 1px solid {rgba('focus', 0.22)}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ border: 1px solid {C['focus']}; background: {C['surface2']}; }}
QPushButton:disabled {{ color: {C['muted']}; border: 1px solid {rgba('focus', 0.08)}; }}
QPushButton#primary {{ color: #ffffff; font-weight: 600; border: 1px solid {rgba('focus', 0.45)}; background: {C['accentStrong']}; }}
QPushButton#primary:hover {{ border: 1px solid {C['focus']}; background: {C['accent']}; }}
QPushButton#primary:disabled {{ background: {C['surface']}; color: {C['muted']}; border: 1px solid transparent; }}
QPushButton#ai {{ color: #ffffff; font-weight: 600; border: 1px solid {rgba('aiText', 0.5)}; background: {C['ai']}; }}
QPushButton#ai:hover {{ background: {C['aiText']}; color: {C['bg0']}; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; color: {C['text2']}; }}
QPushButton#ghost:hover {{ background: {rgba('focus', 0.08)}; color: {C['text']}; }}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{ background: {C['surface2']}; border: 1px solid {rgba('focus', 0.18)};
    border-radius: 10px; padding: 8px 10px; selection-background-color: {C['accent']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{ border: 1px solid {C['focus']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {C['surface2']}; border: 1px solid {rgba('focus', 0.3)}; selection-background-color: {C['accentStrong']}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {rgba('muted', 0.35)}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {rgba('focus', 0.6)}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ height: 0; }}
"""
