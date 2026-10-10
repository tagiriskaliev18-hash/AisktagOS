"""Эффекты Mind для настольных программ на PyQt6: иконки, bounce и живой градиент.

Пример::

    from mindkit import qtfx
    app.setStyleSheet(qtfx.stylesheet())
    btn.setIcon(qtfx.icon("send"))
    qtfx.bounce_on_hover(btn)
    qtfx.shimmer(title_label)        # переливающийся фиолетово-синий фон

PyQt6 импортируется лениво: модуль можно импортировать и без Qt.
"""

from __future__ import annotations

from . import design


def stylesheet() -> str:
    return design.qss()


def icon(name: str, size: int = 48):
    """QIcon иконки Mind с фиолетово-синим градиентом."""
    from PyQt6.QtCore import QByteArray, Qt
    from PyQt6.QtGui import QIcon, QPainter, QPixmap
    from PyQt6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(design.icon_svg(name, size).encode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return QIcon(pm)


def bounce(widget, height: int = 6, duration: int = 520):
    """Один пружинящий прыжок виджета (для появления, уведомлений, клика)."""
    from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSequentialAnimationGroup

    start = widget.pos()
    up = QPropertyAnimation(widget, b"pos", widget)
    up.setDuration(duration // 3)
    up.setStartValue(start)
    up.setEndValue(start - QPoint(0, height))
    up.setEasingCurve(QEasingCurve.Type.OutQuad)
    down = QPropertyAnimation(widget, b"pos", widget)
    down.setDuration(duration - duration // 3)
    down.setStartValue(start - QPoint(0, height))
    down.setEndValue(start)
    down.setEasingCurve(QEasingCurve.Type.OutBounce)
    group = QSequentialAnimationGroup(widget)
    group.addAnimation(up)
    group.addAnimation(down)
    group.start()
    widget._mt_bounce = group  # держим ссылку, иначе анимацию соберёт сборщик мусора
    return group


def bounce_on_hover(widget, height: int = 3):
    """Пружинка при наведении и при нажатии (кнопки, плитки, значки)."""
    from PyQt6.QtCore import QEvent, QObject

    class _Filter(QObject):
        def eventFilter(self, obj, ev):  # noqa: N802 — имя из Qt
            if ev.type() == QEvent.Type.Enter or ev.type() == QEvent.Type.MouseButtonRelease:
                anim = getattr(obj, "_mt_bounce", None)
                if anim is None or anim.state() != anim.State.Running:
                    bounce(obj, height, 420)
            return False

    f = _Filter(widget)
    widget.installEventFilter(f)
    widget._mt_bounce_filter = f
    return f


def shimmer(widget, prop: str = "background", period_ms: int = 6000, extra: str = ""):
    """Переливающийся градиент Mind на фоне виджета (Qt не умеет CSS-анимации — двигаем стопы сами)."""
    from PyQt6.QtCore import QVariantAnimation

    stops = design.tokens()["gradient"]["stops"]

    def paint(v):
        x = float(v)
        parts = ", ".join(f"stop:{round(i / (len(stops) - 1), 2)} {c}" for i, c in enumerate(stops))
        widget.setStyleSheet(
            f"{prop}: qlineargradient(x1:{-x:.3f}, y1:0, x2:{1 - x:.3f}, y2:1, spread:reflect, {parts}); {extra}"
        )

    anim = QVariantAnimation(widget)
    anim.setStartValue(0.0)
    anim.setKeyValueAt(0.5, 1.0)
    anim.setEndValue(0.0)
    anim.setDuration(period_ms)
    anim.setLoopCount(-1)
    anim.valueChanged.connect(paint)
    paint(0.0)
    anim.start()
    widget._mt_shimmer = anim
    return anim
